"""Stop only the dedicated demo worker, observe rescheduling, and restore it."""
import json
import os
import shutil
import sys
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
SSH = ['ssh', '-i', str(Path(os.environ.get('NHIP_SSH_KEY', str(Path.home() / '.ssh/id_rsa_azure'))).expanduser()),
       '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'ConnectTimeout=10',
       '-o', 'StrictHostKeyChecking=yes']
if os.environ.get('NHIP_KNOWN_HOSTS'):
    SSH += ['-o', 'UserKnownHostsFile=' + os.environ['NHIP_KNOWN_HOSTS']]
SSH += ['azureuser@48.218.48.140']
AZ = [shutil.which('az.cmd') or shutil.which('az') or 'az', 'vm']
GROUP = 'rg-nhip-k8s'
if len(sys.argv) != 2 or sys.argv[1] not in ('worker1', 'worker2'):
    raise SystemExit('Usage: python infra/azure/demo-worker.py worker1|worker2')
WORKER = 'nhip-' + sys.argv[1]
SURVIVOR = 'nhip-worker2' if WORKER == 'nhip-worker1' else 'nhip-worker1'
SURVIVOR_HOST = SURVIVOR.removeprefix('nhip-') + '.akaine.io.vn'
results = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'target': WORKER,
           'resource_group': GROUP, 'checks': {}}


def run(command, timeout=45, check=True):
    return subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                          timeout=timeout, check=check)


def vm():
    result = run(AZ + ['show', '--resource-group', GROUP, '--name', WORKER, '--show-details',
        '--query', '{name:name,resourceGroup:resourceGroup,powerState:powerState}',
        '--only-show-errors', '-o', 'json'])
    return json.loads(result.stdout)


def nodes():
    return json.loads(run(SSH + ['kubectl get nodes -o json']).stdout)['items']


def pods():
    return json.loads(run(SSH + ['kubectl get pods -n nhip -o json']).stdout)['items']


def node_ready(name):
    return any(n['metadata']['name'] == name and any(
        c['type'] == 'Ready' and c['status'] == 'True' for c in n['status'].get('conditions', [])
    ) for n in nodes())


def workload_on_survivor():
    found = {'nhip-frontend': 0, 'nhip-backend': 0}
    for pod in pods():
        app = pod['metadata'].get('labels', {}).get('app')
        if app not in found or pod['spec'].get('nodeName') != SURVIVOR or pod['metadata'].get('deletionTimestamp'):
            continue
        if pod['status'].get('phase') == 'Running' and any(
            x['type'] == 'Ready' and x['status'] == 'True' for x in pod['status'].get('conditions', [])
        ):
            found[app] += 1
    return found


def ready_url(host):
    req = urllib.request.Request('https://' + host + '/readyz',
                                 headers={'User-Agent': 'Mozilla/5.0 Nhip-K8s-Check'})
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.status == 200 and json.load(response).get('status') == 'ready'


def wait_until(predicate, timeout, label):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate(): return True
        except (OSError, subprocess.SubprocessError, KeyError, ValueError):
            pass
        time.sleep(5)
    print(label + ': timeout', flush=True)
    return False


subscription = run([AZ[0], 'account', 'show', '--query', 'id', '--only-show-errors', '-o', 'tsv']).stdout.strip()
if subscription != 'e7ab6bf0-a7aa-4012-8751-874d84a8606f':
    raise SystemExit('Unexpected Azure subscription; no VM operation performed.')
baseline = vm()
if baseline['name'] != WORKER or baseline['resourceGroup'].lower() != GROUP or baseline['powerState'] != 'VM running':
    raise SystemExit('Unexpected VM state; no VM operation performed.')
if not all(node_ready(n) for n in ['nhip-cp', 'nhip-worker1', 'nhip-worker2']):
    raise SystemExit('All three nodes must be Ready before the demo.')
deployments = json.loads(run(SSH + ['kubectl get deployments -n nhip -o json']).stdout)['items']
for name in ['nhip-frontend', 'nhip-backend']:
    matches = [d for d in deployments if d['metadata']['name'] == name]
    if len(matches) != 1 or matches[0]['spec'].get('replicas') != 2 or matches[0]['status'].get('readyReplicas') != 2:
        raise SystemExit(name + ' must have exactly two ready replicas before the demo.')
stop_requested = False
stop_finished = False
failure = None
try:
    stop_requested = True
    print('Stopping ' + WORKER + ' temporarily.', flush=True)
    start = time.monotonic()
    # Wait for Azure's power-off operation to finish before the later start.
    run(AZ + ['stop', '--resource-group', GROUP, '--name', WORKER, '--only-show-errors', '-o', 'none'], timeout=180)
    stop_finished = True
    down = wait_until(lambda: not node_ready(WORKER), 150, 'Node NotReady')
    results['checks']['worker_became_not_ready'] = down
    if not down: raise RuntimeError('Worker did not become NotReady')
    print('Worker became NotReady; waiting for rescheduling.', flush=True)
    moved = wait_until(lambda: all(v >= 2 for v in workload_on_survivor().values()), 180, 'Rescheduling')
    results['checks']['replicas_rescheduled_to_survivor'] = moved
    results['observed_failover_seconds'] = round(time.monotonic() - start, 1)
    if not moved: raise RuntimeError('Replicas did not become ready on the remaining worker')
    results['survivor_replicas'] = workload_on_survivor()
    results['checks']['main_ready'] = ready_url('akaine.io.vn')
    results['checks']['surviving_hostname_ready'] = ready_url(SURVIVOR_HOST)
    if not results['checks']['main_ready'] or not results['checks']['surviving_hostname_ready']:
        raise RuntimeError('A surviving endpoint was not ready')
    print('Failover observed: two frontend and two backend replicas ready on ' + SURVIVOR, flush=True)
except Exception as error:
    failure = type(error).__name__ + ': ' + str(error)
    print('Failover check did not complete; restoring worker.', flush=True)
finally:
    if stop_requested:
        if not stop_finished:
            print('Waiting for Azure power-off to finish before attempting recovery.', flush=True)
            stop_finished = wait_until(lambda: vm()['powerState'] in ('VM stopped', 'VM deallocated'),
                                       180, 'VM stopped')
        if not stop_finished:
            print('Power-off not confirmed; inspect Azure and start the worker manually.', flush=True)
            raise SystemExit(1)
        print('Starting ' + WORKER + ' again.', flush=True)
        started = False
        for _ in range(4):
            response = run(AZ + ['start', '--resource-group', GROUP, '--name', WORKER,
                                 '--no-wait', '--only-show-errors', '-o', 'none'], check=False)
            if response.returncode == 0:
                started = True
                break
            time.sleep(10)
        results['checks']['worker_start_requested'] = started
        restored = started and wait_until(lambda: node_ready(WORKER), 300, 'Worker Ready')
        results['checks']['worker_ready_after_restart'] = restored
        if restored:
            print('Worker is Ready; restoring deployment distribution.', flush=True)
            for deployment in ['nhip-frontend', 'nhip-backend']:
                run(SSH + ['kubectl rollout restart deployment/' + deployment + ' -n nhip'])
                run(SSH + ['kubectl rollout status deployment/' + deployment + ' -n nhip --timeout=180s'], timeout=190)
            final = pods()
            distribution = {}
            for app in ['nhip-frontend', 'nhip-backend']:
                distribution[app] = sorted(p['spec'].get('nodeName') for p in final
                    if p['metadata'].get('labels', {}).get('app') == app
                    and p['status'].get('phase') == 'Running'
                    and not p['metadata'].get('deletionTimestamp')
                    and any(c['type'] == 'Ready' and c['status'] == 'True' for c in p['status'].get('conditions', [])))
            results['final_distribution'] = distribution
            results['checks']['distribution_restored'] = all(v == ['nhip-worker1', 'nhip-worker2'] for v in distribution.values())
        else:
            failure = (failure or '') + '; worker recovery not confirmed'
results['failure'] = failure
results['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
(ROOT / ('demo-result-' + sys.argv[1] + '.json')).write_text(json.dumps(results, indent=2), encoding='utf-8')
print(json.dumps(results, ensure_ascii=False), flush=True)
if failure or not all(results['checks'].values()): raise SystemExit(1)
