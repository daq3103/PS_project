"""One bounded Linux build; stop only our build container if the host runs low."""
import pathlib
import runpy
import shutil
import subprocess
import time
import sys
import os

ROOT=pathlib.Path(__file__).resolve().parents[2]
available=runpy.run_path(str(ROOT/'qa-e2e/scripts/safe-build.py'))['available']
GiB=1024**3
NAME='pethome-rescue-workflow-build'


def docker(*args):
    return subprocess.run(['docker',*args],capture_output=True,text=True,encoding='utf-8',errors='replace')


def main():
    sys.stdout.reconfigure(encoding="utf-8",errors="replace")
    if available()<1.2*GiB or shutil.disk_usage(ROOT).free<10*GiB:
        print('Build not started: need 1.2 GiB free RAM and 10 GiB disk.')
        return 2
    result=docker('run','-d','--name',NAME,'--memory=640m','--memory-swap=640m','--cpus=1','--network','ps_project_default',
        '-e','NODE_OPTIONS=--max-old-space-size=384','-e','NEXT_BUILD_CPUS=1','-e','NEXT_TELEMETRY_DISABLED=1','-e','INTERNAL_API_URL=http://fastapi-api:8000',
        '--mount',f'type=bind,source={str(ROOT / "frontend").replace(chr(92),"/")},target=/source,readonly','-w','/app',os.environ.get('PETHOME_BUILD_BASE','pethome-frontend-builddeps'),'sh','-c',
        'set -eu; tar -C /source --exclude=node_modules --exclude=.next --exclude=.env* --exclude=out --exclude=*.tsbuildinfo -cf - . | tar -C /app -xf -; npm run build')
    if result.returncode:
        print(result.stderr)
        return 1
    deadline=time.monotonic()+900
    try:
        while time.monotonic()<deadline:
            if available()<.75*GiB or shutil.disk_usage(ROOT).free<8*GiB:
                print('Stopping only this build: resource reserve reached.')
                return 2
            state=docker('inspect',NAME,'--format','{{.State.Status}} {{.State.ExitCode}} {{.State.OOMKilled}}')
            if state.returncode:
                print(state.stderr)
                return 1
            if state.stdout.startswith('exited'):
                print(docker('logs','--tail','90',NAME).stdout)
                print(state.stdout.strip())
                return 0 if state.stdout.strip()=='exited 0 false' else 1
            time.sleep(1)
        print('Build deadline reached; stopping this build.')
        return 2
    finally:
        state=docker('inspect',NAME,'--format','{{.State.Running}}')
        if state.stdout.strip()=='true':
            docker('stop','--time','5',NAME)


if __name__=='__main__':
    raise SystemExit(main())
