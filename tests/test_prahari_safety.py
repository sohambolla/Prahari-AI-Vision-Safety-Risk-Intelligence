import tempfile
import unittest
from pathlib import Path

from prahari_safety.machine_safety import MachineRegistry
from prahari_safety.perception import legacy_boxes_to_detections
from prahari_safety.risk_engine import RiskEngine
from prahari_safety.store import IncidentStore
from prahari_safety.action_router import ActionRouter


def detection(label, track_id, bbox, confidence=0.9, **extra):
    return {"class": label, "track_id": track_id, "bbox": bbox, "confidence": confidence, **extra}


class RiskEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = RiskEngine({"rules": {}, "max_track_gap_seconds": 1.5})

    def test_fire_requires_ten_tracked_frames(self):
        events = []
        for frame in range(10):
            events = self.engine.evaluate("cam-01", [detection("fire", "F-1", [10, 10, 60, 60])], timestamp=frame * 0.25)
            if frame < 9:
                self.assertEqual(events, [])
        self.assertEqual([item["event_type"] for item in events], ["fire_confirmed"])

    def test_person_down_escalates_after_stillness(self):
        events = []
        for frame in range(13):
            events.extend(self.engine.evaluate("cam-01", [detection("person", "P-1", [100, 100, 300, 180])], timestamp=frame * 0.5))
        event_types = {item["event_type"] for item in events}
        self.assertIn("possible_fall", event_types)
        self.assertIn("person_down", event_types)
        critical = next(item for item in events if item["event_type"] == "person_down")
        self.assertEqual(critical["severity"], "critical")

    def test_falling_load_near_person(self):
        events = []
        for frame in range(5):
            top = 40 + 32 * frame
            detections = [
                detection("suspended load", "L-1", [145, top, 175, top + 40]),
                detection("person", "P-2", [125, 280, 205, 450]),
            ]
            events = self.engine.evaluate("cam-01", detections, timestamp=frame * 0.125, frame_size=(540, 960))
        self.assertIn("falling_object_near_worker", [item["event_type"] for item in events])

    def test_untracked_detections_do_not_raise_temporal_proximity_alerts(self):
        events = []
        detections = [
            detection("person", "P-1", [0, 0, 100, 200]),
            {**detection("car", "fallback-2", [100, 0, 200, 100]), "tracking_confirmed": False},
        ]
        for frame in range(5):
            events.extend(self.engine.evaluate("cam-01", detections, timestamp=frame * 0.25))
        self.assertNotIn("vehicle_pedestrian_proximity", [item["event_type"] for item in events])

    def test_restricted_zone_requires_temporal_confirmation(self):
        zone = [{"zone_id": "restricted", "type": "restricted", "polygon": [[0, 0], [50, 0], [50, 100], [0, 100]]}]
        events = []
        for frame in range(4):
            events = self.engine.evaluate("cam-01", [detection("person", "P-3", [100, 100, 200, 400])], zone, timestamp=frame * 0.25)
            if frame < 3:
                self.assertEqual(events, [])
        self.assertEqual(events[0]["event_type"], "restricted_zone_intrusion")

    def test_exit_blocked_requires_three_frames(self):
        events = []
        detections = [detection("door", "D-1", [0, 0, 100, 100]), detection("forklift", "V-1", [90, 0, 200, 100])]
        for frame in range(3):
            events = self.engine.evaluate("cam-01", detections, timestamp=frame * 0.25)
        self.assertIn("emergency_exit_blocked", [item["event_type"] for item in events])

    def test_unattended_bag_requires_ten_seconds_in_zone(self):
        zone = [{"zone_id": "restricted", "type": "restricted", "polygon": [[0, 0], [50, 0], [50, 100], [0, 100]]}]
        events = []
        for frame in range(41):
            events = self.engine.evaluate("cam-01", [detection("bag", "B-1", [120, 160, 170, 210])], zone, timestamp=frame * 0.25)
            if frame < 40:
                self.assertEqual(events, [])
        self.assertEqual(events[0]["event_type"], "unattended_suspicious_object")


class MachineSafetyTests(unittest.TestCase):
    def test_legacy_ppe_labels_only_mark_explicit_evidence(self):
        detections = legacy_boxes_to_detections([
            ["Person", 0, 0, 100, 200, "0.9"],
            ["NO-Hardhat", 20, 5, 45, 35, "0.8"],
            ["Safety Vest", 20, 60, 80, 120, "0.9"],
        ], {})
        person = next(item for item in detections if item["class"] == "Person")
        self.assertFalse(person["ppe"]["helmet"]["detected"])
        self.assertTrue(person["ppe"]["vest"]["detected"])
        self.assertIsNone(person["ppe"]["gloves"]["detected"])

    def test_interlock_is_fail_closed_and_dry_run(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MachineRegistry(Path(temp) / "machines.json")
            registry.upsert("CNC-01", "cam-01", authorized_person_ids=["worker-7"])
            registry.calibrate("CNC-01", "cam-01", 50, 50)
            blocked = registry.check_interlock("CNC-01", "worker-7", {"helmet": True, "vest": True, "gloves": False})
            allowed = registry.check_interlock("CNC-01", "worker-7", {"helmet": True, "vest": True, "gloves": True})
            self.assertFalse(blocked["start_allowed"])
            self.assertTrue(allowed["start_allowed"])
            self.assertFalse(allowed["physical_actuation"])

    def test_machine_overlap_requires_four_confirmed_frames(self):
        with tempfile.TemporaryDirectory() as temp:
            registry = MachineRegistry(Path(temp) / "machines.json")
            registry.upsert("CNC-01", "cam-01", detection_labels=["machine"])
            events = []
            detections = [
                detection("person", "P-1", [0, 0, 100, 200]),
                detection("machine", "M-1", [30, 60, 70, 130]),
            ]
            for frame in range(4):
                events = registry.evaluate_touches("cam-01", detections, timestamp=frame * 0.25)
                if frame < 3:
                    self.assertEqual(events, [])
            self.assertEqual(events[0]["event_type"], "unauthorized_machine_touch")

    def test_site_router_is_dry_run_even_when_route_is_defined(self):
        router = ActionRouter({"site": {
            "enabled": True, "dry_run": True,
            "zone_routes": {"cam-01:restricted": {"enabled": True, "webhook_url": "http://127.0.0.1/unused"}},
        }})
        result = router.dispatch({"camera_id": "cam-01", "zone_id": "restricted", "severity": "critical"})
        self.assertEqual(result["site"]["mode"], "dry-run")
        self.assertFalse(result["site"]["dispatched"])
        self.assertIn("zone_hooter", result["site"]["simulated_outputs"])

    def test_incidents_are_persisted_and_can_be_acknowledged(self):
        with tempfile.TemporaryDirectory() as temp:
            store = IncidentStore({"root": str(Path(temp) / "media"), "db_path": str(Path(temp) / "events.sqlite3")})
            event = store.record_event({
                "event_id": "event-1", "timestamp": 1000, "camera_id": "cam-01",
                "event_type": "fire_confirmed", "severity": "critical", "title": "Fire detected",
            })
            self.assertEqual(store.list_events()[0]["event_id"], event["event_id"])
            updated = store.update_status("event-1", "ack")
            self.assertEqual(updated["status"], "acknowledged")
            self.assertEqual(store.escalate_unacknowledged(2000), [])
            store.record_event({
                "event_id": "event-2", "timestamp": 1001, "camera_id": "cam-01",
                "event_type": "fire_confirmed", "severity": "critical", "title": "Fire detected",
            })
            escalated = store.escalate_unacknowledged(2000)
            self.assertEqual([item["event_id"] for item in escalated], ["event-2"])


if __name__ == "__main__":
    unittest.main()
