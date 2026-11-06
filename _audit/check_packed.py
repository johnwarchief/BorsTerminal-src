import lzma, os, shutil, sqlite3, tempfile
tmp = os.path.join(tempfile.mkdtemp(), 'market.db')
with lzma.open('market.db.lzma') as src, open(tmp, 'wb') as dst:
    shutil.copyfileobj(src, dst)
c = sqlite3.connect(sqlite3.path.expanduser(tmp) if False else tmp.replace(os.sep, '/'), timeout=30)
rows = [("SELECT MAX(d_even) FROM tape_history", 'tape.max_d_even'),
        ("SELECT COUNT(*), COUNT(DISTINCT d_even) FROM tape_history", 'tape.rows/sessions'),
        ("SELECT MAX(d_even) FROM market_watch", 'watch.max_d_even'),
        ("SELECT COUNT(*) FROM financial_statements", 'fs.rows'),
        ("SELECT MAX(d_even) FROM daily_prices", 'daily.max_d_even')]
for q, label in rows:
    print(label, c.execute(q).fetchone())
c.close(); os.remove(tmp)
