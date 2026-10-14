"""Dry-run machine start interlock. This module never toggles a physical relay."""


class SafetyInterlock:
    def __init__(self, machine_registry):
        self.machine_registry = machine_registry

    def evaluate_start(self, machine_id, person_id, ppe):
        result = self.machine_registry.check_interlock(machine_id, person_id, ppe)
        result["requested_action"] = "start"
        result["physical_actuation"] = False
        return result
