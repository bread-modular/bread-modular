"""Single-run Bubblewrap containment. No fallback, no host Java invocation."""
import json
import os
import socket
from pathlib import Path

from safety import RUNTIME, checked, digest, require, run_process, safe_path, write_json

SETTINGS = {
    "gui.enabled": False, "api_server.enabled": False, "mcp_server.enabled": False,
    "usage_and_diagnostic_data.disable_analytics": True, "profile.allow_telemetry": False,
    "logging.console.level": "DEBUG", "logging.file.enabled": False,
    "router.autorouter.max_passes": 10,
    "router.optimizer.enabled": False, "router.fanout.enabled": False,
    "router.copperToEdgeClearanceUm": 500, "router.automatic_neckdown": False,
}
PROBE = r'''import errno,json,os,socket,sys
host,port = sys.argv[1],int(sys.argv[2])
ns=os.readlink('/proc/self/ns/net')
interfaces=[x.split(':')[0].strip() for x in open('/proc/net/dev') if ':' in x]
errors={}
for key,addr in [('egress',('1.1.1.1',443)),('host_loopback',('127.0.0.1',port))]:
    with socket.socket() as s:
        s.settimeout(1)
        try:
            s.connect(addr)
            raise RuntimeError('network probe unexpectedly connected')
        except OSError as e:
            errors[key]=e.errno
assert errors['egress'] in (errno.ENETUNREACH,errno.EHOSTUNREACH),errors
assert errors['host_loopback'] in (errno.ENETUNREACH,errno.EHOSTUNREACH,errno.ECONNREFUSED),errors
assert ns != host and set(interfaces) <= {'lo'},(ns,host,interfaces)
readonly={}
for path in ['/runtime/provenance.json','/usr/probe-write','/outside-write']:
    try:
        with open(path,'a') as f: pass
        raise RuntimeError('read-only sandbox write succeeded: '+path)
    except OSError as e:
        assert e.errno == errno.EROFS,(path,e.errno)
        readonly[path]=e.errno
assert not os.path.exists('/home/azero'), 'host home exposed'
with open('/run/probe-write','x') as f: f.write('only run directory writable')
print(json.dumps({'status':'verified','net_namespace':ns,'host_net_namespace':host,
                 'interfaces':interfaces,'connection_errors':errors,'readonly_errors':readonly,
                 'home':os.environ['HOME'],'tmp':os.environ['TMPDIR']}))
'''


def command(run, executable):
    run = safe_path(run)
    require(Path('/usr/bin/bwrap').is_file(), "Bubblewrap missing; no online fallback")
    argv = ['/usr/bin/bwrap', '--die-with-parent', '--new-session', '--unshare-net',
            '--unshare-pid', '--unshare-ipc', '--unshare-uts', '--cap-drop', 'ALL',
            '--ro-bind', '/usr', '/usr']
    for path in ['/lib', '/lib64']:
        if Path(path).exists():
            argv += ['--ro-bind', path, path]
    argv += ['--hostname', 'routing-smoke', '--dir', '/etc',
             '--ro-bind', str(safe_path(run/'hosts')), '/etc/hosts',
             '--ro-bind', str(safe_path(run/'nsswitch.conf')), '/etc/nsswitch.conf']
    if Path('/etc/ld.so.cache').is_file():
        argv += ['--ro-bind', '/etc/ld.so.cache', '/etc/ld.so.cache']
    argv += ['--ro-bind', str(safe_path(RUNTIME)), '/runtime',
             '--bind', str(run), '/run']
    for name in ['source', 'before']:
        if (run/name).exists():
            argv += ['--ro-bind', str(safe_path(run/name)), '/run/'+name]
    dsn = run/('input-'+run.name+'.dsn')
    if dsn.exists():
        argv += ['--ro-bind', str(safe_path(dsn)), '/run/'+dsn.name]
    argv += ['--proc', '/proc', '--dev', '/dev', '--remount-ro', '/proc',
             '--clearenv', '--setenv', 'PATH', '/usr/bin', '--setenv', 'LANG', 'C.UTF-8',
             '--setenv', 'TZ', 'UTC', '--setenv', 'HOME', '/run/home',
             '--setenv', 'XDG_CONFIG_HOME', '/run/xdg/config',
             '--setenv', 'XDG_CACHE_HOME', '/run/xdg/cache',
             '--setenv', 'XDG_DATA_HOME', '/run/xdg/data',
             '--setenv', 'TMPDIR', '/run/tmp', '--chdir', '/run', '--remount-ro', '/', '--']
    return argv + list(map(str, executable))


def setup(run, timeout=15):
    for name in ['home', 'tmp', 'xdg/config', 'xdg/cache', 'xdg/data', 'freerouting-config']:
        safe_path(run/name).mkdir(parents=True, exist_ok=False)
    (run/'network-probe.py').write_text(PROBE)
    (run/'hosts').write_text('127.0.0.1 localhost routing-smoke\n::1 localhost routing-smoke\n')
    (run/'nsswitch.conf').write_text('hosts: files\n')
    config = {"version": "2.5.0", "profile": {
        "id": "e2e3ee44-369d-4f7e-8d35-78275e33c54d", "email": "",
        "allow_telemetry": False, "allow_contact": False}}
    for key,value in SETTINGS.items():
        target = config
        parts = key.split('.')
        for part in parts[:-1]:
            target = target.setdefault(part,{})
        target[parts[-1]] = value
    write_json(run/'freerouting-config/freerouting.json', config, exclusive=True)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); listener.listen(1)
        port = listener.getsockname()[1]
        rec = run_process(command(run, ['/usr/bin/python3', '-I', '/run/network-probe.py',
                          os.readlink('/proc/self/ns/net'), port]), run/'logs', 'network-probe', timeout)
        checked(rec)
    data = json.loads((run/'logs/network-probe.stdout.log').read_text())
    require(data['status'] == 'verified', 'sandbox probe not verified')
    write_json(run/'sandbox.json', data, exclusive=True)
    return data, rec


def java_command(run, java, jar, flags):
    j = '/runtime/' + str(java.relative_to(RUNTIME))
    a = '/runtime/' + str(jar.relative_to(RUNTIME))
    return command(run, [j, '-Xmx512m', '-XX:ActiveProcessorCount=2', '-Djava.awt.headless=true',
                         '-Duser.home=/run/home', '-Djava.io.tmpdir=/run/tmp', '-jar', a] + flags)


def flags():
    return ['-da', '--user_data_path=/run/freerouting-config'] + [
        '--'+key+'='+ (str(value).lower() if isinstance(value, bool) else str(value))
        for key,value in SETTINGS.items()]


def validate_logs(run, name):
    logs = ''.join((run/'logs'/f'{name}.{stream}.log').read_text(errors='replace') for stream in ['stdout','stderr'])
    # Unknown settings often just warn and exit 0 upstream: explicitly reject them.
    bad = ['unknown settings property', 'unknown command line argument', 'failed to set property',
           'failed to apply', 'unrecognized', 'deprecated', 'exception in thread']
    require(not any(x in logs.lower() for x in bad), 'Freerouting rejected/ignored a setting; inspect logs')
    require('Freerouting v2.5.0' in logs, 'runtime version banner mismatch')
    require('Analytics are disabled' in logs, 'analytics opt-out not evidenced by runtime')
    return logs


def preflight(run, java, jar, timeout=30):
    # Help exercises GlobalSettings' actual reflection parser without routing.
    rec = run_process(java_command(run, java, jar, flags()+['--help']), run/'logs', 'freerouting-help', timeout)
    checked(rec); logs = validate_logs(run, 'freerouting-help')
    require('Usage:' in logs or '-de' in logs, 'missing actual help output')
    # Default JSON is saved BEFORE CLI flags are applied in 2.5.0. Do not
    # misrepresent it as an effective snapshot. Seed our isolated safety settings
    # as an additional opt-out; real merged router settings are checked in result JSON.
    config = safe_path(run/'freerouting-config/freerouting.json')
    data = json.loads(config.read_text())
    for key,value in SETTINGS.items():
        target = data
        parts = key.split('.')
        for part in parts[:-1]:
            target = target.setdefault(part,{})
        target[parts[-1]] = value
    write_json(config, data)
    return rec


def route(run, java, jar, timeout=120):
    require(not safe_path(run/'result.ses').exists(), 'SES output overwrite refused')
    extra = ['--router.result_json_path=/run/freerouting-result.json']
    rec = run_process(java_command(run, java, jar, flags()+extra+
                      ['-de', '/run/input-'+run.name+'.dsn', '-do', '/run/result.ses']),
                      run/'logs', 'freerouting-route', timeout)
    checked(rec); validate_logs(run, 'freerouting-route')
    result = json.loads(safe_path(run/'freerouting-result.json').read_text())
    settings = result['settings_snapshot']
    for key,value in SETTINGS.items():
        if not key.startswith('router.'):
            continue
        target = settings
        for part in key.split('.')[1:]:
            part = {'copperToEdgeClearanceUm': 'copper_to_edge_clearance_um'}.get(part,part)
            require(part in target, f'effective router field missing: {key}')
            target = target[part]
        require(target == value, f'effective router flag mismatch: {key}: {target}')
    require(result['exit_code'] == 0 and result['final_state'] == 'COMPLETED' and
            result['app_version'] == '2.5.0' and result['output_written'], 'Freerouting job did not succeed')
    require(result['fixture']['sha256'] == digest(run/('input-'+run.name+'.dsn')) and
            result['fixture']['filename'] == 'input-'+run.name+'.dsn', 'router result/DSN association mismatch')
    require(not settings.get('validation_warnings'), 'router settings validation warnings')
    write_json(run/'effective-settings.json', {"requested": SETTINGS, "actual_router": settings,
               "verification": "native Freerouting merged job result; help parser verified non-router flags"}, exclusive=True)
    return rec, result
