import json
import subprocess
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    # First get shallow tree to find Messages container ref
    res = subprocess.check_output(
        ['python', 'tools/agent_desktop_runner.py', 'snapshot', '--app', 'Telegram', '-i', '--max-depth', '6'],
        encoding='utf-8'
    )
    data = json.loads(res)
    
    messages_ref = None
    def find_container_ref(node):
        nonlocal messages_ref
        name = node.get('name', '')
        ref = node.get('ref_id', '')
        if name == 'Messages':
            messages_ref = ref
            return
        for c in node.get('children', []):
            find_container_ref(c)

    find_container_ref(data.get('data', {}).get('tree', {}))
    print(f"Messages container ref: {messages_ref}")
    if not messages_ref:
        return

    # Drill into Messages container
    res_root = subprocess.check_output(
        ['python', 'tools/agent_desktop_runner.py', 'snapshot', '--root', messages_ref, '-i', '--max-depth', '3'],
        encoding='utf-8'
    )
    data_root = json.loads(res_root)
    tree_root = data_root.get('data', {}).get('tree', {})
    children = tree_root.get('children', [])
    print(f"Total messages in root: {len(children)}")
    for i, c in enumerate(children):
        c_name = c.get('name', '').replace('\n', ' ')[:80]
        c_ref = c.get('ref_id', '')
        avail = c.get('available_actions', [])
        if 'Indicator' in c_name or 'Photo' in c_name:
            print(f"  [{i:03d}] {c_ref} ({avail}) | {c_name}")

if __name__ == '__main__':
    main()
