from bs4 import BeautifulSoup

with open("debug_page_1.html", "r") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
links = soup.find_all("a")
print(f"Total links: {len(links)}")

count = 0
for link in links:
    href = link.get("href", "")
    if "details" in href:
        print(f"FOUND: {href}")
        print(f"  Text: {link.get_text().strip()}")
        print(f"  Parent: {link.parent.name} class={link.parent.get('class')}")
        count += 1

print(f"Total details links: {count}")

# Also check for feed items
items = soup.find_all(class_="feed-item-report")
print(f"Feed items found: {len(items)}")

if items:
    print("\n--- First Feed Item Structure ---")
    print(items[0].prettify())

