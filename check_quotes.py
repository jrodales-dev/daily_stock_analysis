import sys
sys.stdout.reconfigure(encoding='utf-8')

try:
    with open('src/notification.py', 'r', encoding='utf-8') as f:
        source = f.read()
    
    lines = source.split('\n')
    count = 0
    for i, line in enumerate(lines):
        c = line.count('\"\"\"')
        if c > 0:
            count += c
            print(f"Line {i+1} has {c} quotes, total: {count}, parity: {count % 2}")
        if i + 1 == 961:
            break
except Exception as e:
    print(e)
