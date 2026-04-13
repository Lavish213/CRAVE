import requests
import time

from app.services.menu.menu_extraction_router import extract_menu
from app.services.menu.normalization.menu_normalizer import normalize_menu_item
from app.services.menu.canonical.menu_claim_builder import build_menu_claims
from app.services.menu.canonical.menu_canonicalizer import canonicalize_menu_claims


restaurants = [
"https://www.chipotle.com/menu",
"https://www.panerabread.com/en-us/menu.html",
"https://www.tacobell.com/food",
"https://www.wendys.com/menu",
"https://www.mcdonalds.com/us/en-us/full-menu.html",
"https://www.bk.com/menu",
"https://www.dominos.com/en/pages/order/menu",
"https://www.pizzahut.com/menu",
"https://www.kfc.com/menu",
"https://www.popeyes.com/menu",

"https://www.chilis.com/menu",
"https://www.applebees.com/en/menu",
"https://www.outback.com/menu",
"https://www.redlobster.com/menu",
"https://www.olivegarden.com/menu",
"https://www.longhornsteakhouse.com/menu",
"https://www.cheesecakefactory.com/menu",
"https://www.bjsrestaurants.com/menu",
"https://www.crackerbarrel.com/menu",
"https://www.buffalowildwings.com/menu",

"https://www.shakeshack.com/menu",
"https://www.sweetgreen.com/menu",
"https://www.cava.com/menu",
"https://www.qdoba.com/menu",
"https://www.moes.com/menu",
"https://www.firehousesubs.com/menu",
"https://www.jersey-mikes.com/menu",
"https://www.potbelly.com/menu",

"https://www.starbucks.com/menu",
"https://www.dunkindonuts.com/en/menu",
"https://www.peets.com/menu",

"https://www.in-n-out.com/menu",
"https://www.fiveguys.com/menu",
"https://www.smashburger.com/menu",

"https://www.elpolloloco.com/menu",
"https://www.deltaco.com/menu",

"https://www.subway.com/en-us/menu",
"https://www.quiznos.com/menu",

"https://www.thehalalguys.com/menu",
"https://www.nandos.com/menu",
"https://www.wagamama.com/menu",

"https://www.pandaexpress.com/menu",
"https://www.peiwei.com/menu",
"https://www.pfchangs.com/menu",

"https://www.cpk.com/menu",
"https://www.dennys.com/menu",
"https://www.ihop.com/en/menu",

"https://www.firstwatch.com/menu",
"https://www.anotherbrokenegg.com/menu",

"https://www.hooters.com/menu",
"https://www.missionbbq.com/menu",
"https://www.torchtystacos.com/menu",

"https://www.wingstop.com/menu",
"https://www.zaxbys.com/menu",
"https://www.krystal.com/menu"
]


success = 0
fail = 0
total_items = 0


for url in restaurants:

    print("\n==============================")
    print("Testing:", url)

    try:

        html = requests.get(url, timeout=20).text
        print("HTML length:", len(html))

        extracted = extract_menu(html, url)
        print("Extracted:", len(extracted))

        normalized = [normalize_menu_item(i) for i in extracted]
        print("Normalized:", len(normalized))

        claims = build_menu_claims(normalized)
        print("Claims:", len(claims))

        menu = canonicalize_menu_claims(claims)

        print("Sections:", len(menu.sections))
        print("Canonical items:", menu.item_count)

        if menu.item_count > 0:
            success += 1
            total_items += menu.item_count
        else:
            fail += 1

    except Exception as e:

        print("FAILED:", str(e))
        fail += 1

    time.sleep(1)


print("\n==============================")
print("FINAL RESULTS")
print("==============================")

print("Sites tested:", len(restaurants))
print("Success:", success)
print("Fail:", fail)

if success > 0:
    print("Avg items per successful site:", total_items // success)