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
            rows = {}
            for c in children:
                if c.get('role') == 'row':
                    rows[c.get('name', '')] = c.get('value', '')
            messages.append({
                'ref': ref,
                'summary': name.replace('\n', ' -- '),
                'rows': rows
            })
        for c in children:
            walk(c)

    walk(data.get('data', {}).get('tree', {}))

    print(f"Total messages extracted: {len(messages)}")

    catalog = []
    current_item = {}

    for m in messages:
        rows = m['rows']
        media_type = rows.get('Media type', '')
        msg = rows.get('Message', '')
        filename = rows.get('Filename', '')
        dimensions = rows.get('Dimensions', '')
        time_str = rows.get('Time', '')

        if media_type == 'Photo' or 'Indicator' in msg or dimensions:
            item = {
                'title': msg.strip() if msg else 'Photo without caption',
                'dimensions': dimensions,
                'time': time_str,
                'files': []
            }
            catalog.append(item)
        elif filename:
            if catalog:
                catalog[-1]['files'].append({
                    'filename': filename,
                    'size': rows.get('File size', ''),
                    'downloaded': rows.get('Download', '')
                })
            else:
                catalog.append({
                    'title': filename,
                    'dimensions': '',
                    'time': time_str,
                    'files': [{'filename': filename, 'size': rows.get('File size', ''), 'downloaded': rows.get('Download', '')}]
                })

    with open('telegram_indicators_catalog.json', 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(f"Catalog created with {len(catalog)} indicator items! Saved to telegram_indicators_catalog.json")
    for i, it in enumerate(catalog, 1):
        fls = ", ".join(f['filename'] for f in it['files'])
        print(f"[{i:02d}] {it['title'].splitlines()[0][:60]} | Files: {fls}")

if __name__ == '__main__':
    main()
