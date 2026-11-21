import sys,time
raw=sys.stdin.buffer.read()
time.sleep(.03)
sys.stdout.buffer.write(raw.upper());sys.stdout.buffer.flush()
