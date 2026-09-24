from pathlib import Path
import re

text = Path("audiobooks/projects/witcher1/extracted/chapter_013.md").read_text(encoding="utf-8")

m1 = text.find("Allow me, Geralt sir")
m2 = text.find("The soldiers surrounded the glade")
m3 = text.find("\nII\n")

c1 = text[:m1].strip()
c2 = text[m1:m2].strip()
c3 = text[m2:m3].strip()
c4 = text[m3:].strip()

print("C1 words:", len(c1.split()), "| First line:", c1.splitlines()[0][:50])
print("C2 words:", len(c2.split()), "| First line:", c2.splitlines()[0][:50])
print("C3 words:", len(c3.split()), "| First line:", c3.splitlines()[0][:50])
print("C4 words:", len(c4.split()), "| First line:", c4.splitlines()[0][:50])
