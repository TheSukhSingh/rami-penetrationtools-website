import subprocess
import os

def run_scan(data):

    targets = data.get('dnsx-file')
    manual = data.get('dnsx-manual')
    if manual and not targets:
        targets = '/tmp/dnsx_manual_targets.txt'
        with open(targets, 'w') as f:
            f.write('\n'.join(line.strip() for line in manual.splitlines() if line.strip()))

    if not targets or not os.path.exists(targets):
        return {"status": "error", "message": "Targets file missing or does not exist."}

    flags = []
    # Always show record type in output
    flags.append("-resp")
    flags.append("-no-color")

    # Silent by default
    sil = data.get('silent', '').strip().lower()
    if sil == '' or sil == 'y':
        flags.append('-silent')

    # Collect record types from the frontend list
    rtypes = data.get('dnsx-record-types', [])
    if isinstance(rtypes, str):
        rtypes = [rtypes]

    seen = set()
    for r in rtypes:
        r = r.lower()
        if r in ('a','aaaa','cname','mx','ns','txt') and r not in seen:
            flags.append(f"-{r}")
            seen.add(r)

    # Threads and retry defaults
    threads = data.get('dnsx-threads', '').strip() or '50'
    retry   = data.get('dnsx-retry', '').strip()   or '3'

    flags.extend(['-t', threads, '-retry', retry])

    # Build and log command
    command = ['dnsx'] + flags + ['-l', targets]
    # only show the basename in the UI
    display = ['dnsx'] + flags + ['-l', os.path.basename(targets)]
    command_str = f"hacker@gg > {' '.join(display)}"

    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            return {"status": "error", "message": f"dnsx error:\n{result.stderr.strip()}"}
        output = result.stdout.strip() or 'No output captured.'
        return {"status": "success", "command": command_str, "output": output}

    except FileNotFoundError:
        return {"status": "error", "message": "dnsx is not installed or not found in PATH."}
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}
