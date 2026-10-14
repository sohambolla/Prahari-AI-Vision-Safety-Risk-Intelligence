import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { spawn } from 'node:child_process'
import { createConnection } from 'node:net'
import { fileURLToPath } from 'node:url'

const projectRoot = fileURLToPath(new URL('..', import.meta.url))
const visionServerPath = fileURLToPath(new URL('../prahari_live_server.py', import.meta.url))

function startVisionServer() {
  let backendProcess
  let stopping = false

  const stopBackend = () => {
    stopping = true
    if (backendProcess && backendProcess.exitCode === null) backendProcess.kill()
  }

  const launchBackend = (server) => {
    if (stopping || backendProcess) return
    const python = process.env.PRAHARI_PYTHON || 'python'
    server.config.logger.info(`Starting PRAHARI vision server with ${python}...`)
    backendProcess = spawn(python, [visionServerPath], {
      cwd: projectRoot,
      stdio: 'inherit',
      windowsHide: true,
    })
    backendProcess.once('error', error => {
      server.config.logger.error(`Could not start PRAHARI vision server: ${error.message}`)
    })
    backendProcess.once('exit', (code, signal) => {
      if (!stopping && code !== 0) {
        server.config.logger.error(`PRAHARI vision server exited (code ${code ?? 'none'}, signal ${signal ?? 'none'}).`)
      }
    })
  }

  return {
    name: 'prahari-vision-server',
    configureServer(server) {
      server.httpServer?.once('close', stopBackend)
      if (process.env.PRAHARI_AUTOSTART_VISION === '0') {
        server.config.logger.info('PRAHARI vision server auto-start is disabled.')
        return
      }

      const probe = createConnection({ host: '127.0.0.1', port: 8000 })
      let responseText = ''
      let responseHandled = false
      probe.setTimeout(750)
      probe.once('connect', () => {
        probe.write('GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n')
      })
      probe.on('data', chunk => { responseText += chunk.toString() })
      probe.once('end', () => {
        responseHandled = true
        const responseBody = responseText.split('\r\n\r\n').slice(1).join('\r\n\r\n')
        probe.destroy()
        try {
          const payload = JSON.parse(responseBody)
          if (payload.vision_api === 2) {
            server.config.logger.info('PRAHARI vision server v2 is already listening on port 8000.')
            return
          }
        } catch {}
        server.config.logger.error('An older or incompatible vision server is listening on port 8000. Restart it to enable open-vocabulary segmentation.')
      })
      probe.once('timeout', () => {
        probe.destroy()
        if (!responseHandled) launchBackend(server)
      })
      probe.once('error', () => {
        probe.destroy()
        if (!responseHandled) launchBackend(server)
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), startVisionServer()],
})
