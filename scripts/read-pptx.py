"""Read-only dump of slide text, sizes and media: read-pptx.py FILE.pptx"""
import re, sys, zipfile
sys.stdout.reconfigure(encoding="utf-8")
z = zipfile.ZipFile(sys.argv[1])
names = z.namelist()
pres = z.read("ppt/presentation.xml").decode("utf8")
print("size", re.search(r'<p:sldSz[^>]*>', pres).group(0))
slides = sorted([n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)], key=lambda n: int(re.findall(r"\d+", n)[0]))
for n in slides:
    x = z.read(n).decode("utf8")
    texts = [" ".join(re.findall(r"<a:t>([^<]*)</a:t>", p)) for p in re.findall(r"<a:p>.*?</a:p>", x, flags=re.S)]
    print("\n==", n, "pics:", x.count("<p:pic>"), "shapes:", x.count("<p:sp>"))
    for t in texts:
        if t.strip(): print("  -", t)
print("\nmedia:", [(n, z.getinfo(n).file_size) for n in names if "media" in n])
print("layouts:", len([n for n in names if "slideLayouts/slideLayout" in n and n.endswith(".xml")]))
