"""Download a public Google Drive file, handling the virus-scan confirm page."""
import re, sys, requests

def download(file_id, dest):
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    url = "https://drive.usercontent.google.com/download"
    r = s.get(url, params={"id": file_id, "export": "download"}, allow_redirects=True, timeout=120)
    if "text/html" in r.headers.get("content-type", ""):
        # confirm form -> resubmit with hidden fields
        fields = dict(re.findall(r'name="([^"]+)"\s+value="([^"]*)"', r.text))
        if not fields:
            print(r.text[:500]); raise SystemExit("no confirm form found")
        r = s.get(url, params=fields, stream=True, timeout=600)
    total = 0
    with open(dest, "wb") as fh:
        for chunk in r.iter_content(1 << 20):
            fh.write(chunk); total += len(chunk)
    print(f"{dest}  {total/1e6:.1f} MB  ct={r.headers.get('content-type')}")

if __name__ == "__main__":
    download(sys.argv[1], sys.argv[2])
