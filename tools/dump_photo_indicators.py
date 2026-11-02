import json
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    with open('telegram_snap.json', 'r', encoding='utf-16') as f:
        data = json.load(f)

    messages = []
    def walk(node):
        role = node.get('role', '')
        name = node.get('name', '')
        ref = node.get('ref_id', '')
        children = node.get('children', [])
        if role == 'option' and any(k in name for k in ['Photo', 'File', 'Indicator', 'Sent', 'Received', 'Message']):
            rows = {c.get('name', ''): c.get('value', '') for c in children if c.get('role') == 'row'}
            messages.append({
                'ref': ref,
                'media': rows.get('Media type', ''),
                'dimensions': rows.get('Dimensions', ''),
                'filename': rows.get('Filename', ''),
                'message': rows.get('Message', ''),
                'time': rows.get('Time', '')
            })
        for c in children:
            walk(c)

    walk(data.get('data', {}).get('tree', {}))

    photo_indicators = [m for m in messages if m['media'] == 'Photo' or m['dimensions']]
    print(f"Total photo indicators in chat: {len(photo_indicators)}")

    for i, p in enumerate(photo_indicators, 1):
        msg_preview = p['message'].replace('\n', ' ')[:100]
        ref = p['ref']
        dims = p['dimensions']
        print(f"[{i:02d}] {ref} | Dim: {dims} | {msg_preview}")

if __name__ == '__main__':
    main()
