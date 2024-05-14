import requests
import subprocess as sp
from pathlib import Path
from unidecode import unidecode
from bs4 import BeautifulSoup, Comment

from ocrmypdf import ocr
from reportlab.pdfgen import canvas

module_dir = Path(__file__).parent


def Get(url, **kwargs):
    kwargs["headers"] = {
        **kwargs.get("headers", {}),
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"
        " AppleWebKit/537.36 (KHTML, like Gecko)"
        " Chrome/109.0.0.0 Safari/537.36",
    }
    return requests.get(url, **kwargs)


class Document(dict):
    def __init__(doc, doc_ini):
        super().__init__(
            {
                "BIB": ".",
                "type": None,
                "ref": None,
                "FILE": None,
                "ext": "",
                "bib": None,
                "txt": None,
                "alternate_bib": None,
                "tags": [],
                **doc_ini,
            }
        )

        doc.path.parent.mkdir(parents=True, exist_ok=True)
        return

    @property
    def path(doc):
        return Path(doc["BIB"]) / doc["type"] / (doc["ref"] + doc["ext"])

    def mess(doc, m):
        ext = f'({doc["ext"].lstrip(".")}) ' if doc["ext"] else ""
        print(f'{doc["type"]}: {doc["ref"]} {ext}> {m}')
        return

    def toggle(doc):
        if "HIDDEN" in doc["tags"]:
            doc["tags"].remove("HIDDEN")
        else:
            doc["tags"].append("HIDDEN")
        return

    def get(doc, what):
        if "doc" in what:
            if getattr(doc, "FILE", None):
                fl = Path(doc["FILE"])
                doc["ext"] = fl.suffix
                content = fl.read_bytes()
            else:
                content = getattr(doc, doc["type"])()
            if content:
                file = Path(doc.path)
                file.write_bytes(content)
                if "PLACEHOLDER" in doc["tags"]:
                    doc["tags"].remove("PLACEHOLDER")
            else:
                doc.placeholder()
        elif "bib" in what:
            bib_entry = getattr(doc, "bib_" + doc["type"])()
            doc["bib"] = format_bib(bib_entry)
        elif "txt" in what:
            doc.get_txt()
            if doc["txt"] == "":
                doc.make_ocr()
                doc.get_txt()
        doc.mess(f"Added {what}.")
        return

    def placeholder(doc):
        doc.mess("File unavailable. Making placeholder.")
        if "PLACEHOLDER" not in doc["tags"]:
            doc["tags"].append("PLACEHOLDER")
        doc["ext"] = ".pdf"
        text = f'{doc["type"]}: {doc["ref"]}'
        pdf = canvas.Canvas(str(doc.path), pagesize=(len(text) * 12, 12))
        pdf.drawString(1, 1, text)
        pdf.save()
        return

    def arxiv(doc):
        pdf = Get("https://arxiv.org/pdf/" + doc["ref"])
        if (
            "We are now attempting to automatically"
            " create some PDF from the article's source." in pdf.text
            or "PDF unavailable ..." in pdf.text
        ):
            return
        doc["ext"] = ".pdf"
        return pdf.content

    def doi(doc):
        link = f'https://sci-hub.ee/{doc["ref"]}'
        page = Get(link).text
        if not page:
            return

        page = BeautifulSoup(page, features="lxml")

        comments = page.find_all(
            string=lambda text: isinstance(text, Comment)
        )
        links = []
        pages = (page, *[BeautifulSoup(c, features="lxml") for c in comments])
        for p in pages:
            links.extend(
                dl["src"]
                for dl in p.find_all(
                    lambda tag: tag.has_attr("id") and tag.has_attr("src")
                )
            )
            links.extend(
                db["onclick"].split("'")[1]
                for db in p.find_all(
                    lambda tag: tag.has_attr("href")
                    and tag.has_attr("onclick")
                )
            )

        def cleanup_link(lnk):
            if lnk.startswith("//"):
                lnk = "http:" + lnk
            elif lnk.startswith("/"):
                lnk = "http://sci-hub.se" + lnk
            elif "\\" in lnk:
                lnk = lnk.replace("\\", "")
            return lnk

        links = [cleanup_link(lnk) for lnk in links]

        if not links:
            return

        for link in links:
            if doc["ref"] in link:
                break
        else:
            for link in links:
                if "download=true" in link:
                    break
            else:
                for link in links:
                    if "pdf" in link:
                        break
                else:
                    link = links[0]

        print(f"Downloading from:\n[1] {link}")
        links.remove(link)
        if links:
            links = [f"[{i+2}] {lnk}" for i, lnk in enumerate(links)]
            links = "\n".join(links)
            print(f"Alternatives:\n{links}")

        doc["ext"] = ".pdf"

        headers = {
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
            "Accept": "application/pdf",
            "Accept-Language": "en-US, en;q=0.5",
        }

        pdf = Get(link, headers=headers).content

        return pdf

    def isbn(doc):
        url = "http://gen.lib.rus.ec"

        idinfo = BeautifulSoup(
            Get(url + "/search.php", params={"req": doc["ref"]}).text,
            features="lxml",
        )
        ids = []
        for tag in idinfo.find_all(
            lambda tag: tag.name == "a" and tag.has_attr("id")
        ):
            ids.append(tag["id"])

        params = {
            "ids": ",".join(ids),
            "fields": "*",
        }
        json_data = Get(url + "/json.php", params=params).json()

        for i in range(len(json_data) - 1, -1, -1):
            if json_data[i]["extension"] not in ("djvu", "pdf", "epub"):
                del json_data[i]

        json_data.sort(reverse=True, key=lambda a: a["timeadded"])

        if len(json_data):
            cond = [
                lambda a: a["scanned"] == "" and a["searchable"] == "1",
                lambda a: a["scanned"] == "",
                lambda a: True,
            ]

            c = 0
            while c < 3:
                for i in range(len(json_data)):
                    if cond[c](json_data[i]):
                        json_info = json_data[i]
                        break
                c += 1

            url = "http://library.lol/main/" + json_info["md5"]
            dl = BeautifulSoup(Get(url).text, features="lxml")
            dl = dl.find(
                lambda tag: tag.name == "a"
                and "GET" in tag.text
                and tag.has_attr("href")
            )["href"]

            doc["ext"] = "." + json_info["extension"]
            doc.mess(f'Doc found (ext:{doc["ext"]}), downloading...')

            docu = Get(dl).content
            if ".djvu" in doc["ext"] and "1" not in json_info["searchable"]:
                doc.mess("Converting downloaded djvu file...")
                psdoc = sp.check_output(["djvups"], input=docu, text=True)
                docu = sp.check_output(["ps2pdf"], input=psdoc, text=True)
                doc["ext"] = ".pdf"
        else:
            doc.mess("Book does not exist in Online Library.")
            return
        return docu

    def bib_doi(doc):
        return Get(
            "http://dx.doi.org/" + doc["ref"],
            headers={"Accept": "text/bibliography; style=bibtex"},
        ).content.decode("utf-8")

    def bib_isbn(doc):
        link = "https://lead.to/amazon/com/dl-bib-com.html?key="
        bib_entry = Get(link + doc["ref"]).text
        if "There is no result." in bib_entry:
            bib_entry = Get(link + doc["alternate_bib"]).text
        if "There is no result." in bib_entry:
            return
        return bib_entry

    def bib_arxiv(doc):
        b = BeautifulSoup(
            Get(
                "http://export.arxiv.org/api/query?id_list=" + doc["ref"]
            ).text,
            features="xml",
        )
        authors = " and ".join([x.text for x in b.find_all("name")])
        title = b.find_all("title")[-1].text
        year = b.find("published").text.split("-")[0]
        bib_entry = """
        @article{%s,
        author = {%s},
        title = {%s},
        year = {%s},
        archivePrefix = {arXiv},
        eprint = {%s},
        }""" % (
            doc["ref"],
            authors,
            title,
            year,
            doc["ref"],
        )
        return bib_entry

    def get_txt(doc):
        if ".epub" in doc["ext"]:
            txt = sp.check_output(["epub2txt", doc.path], text=True)
        elif ".djvu" in doc["ext"]:
            txt = sp.check_output(
                ["djvutxt", "--page=1-12", doc.path], text=True
            )
        elif ".pdf" in doc["ext"]:
            txt = sp.check_output(
                ["pdftotext", "-q", "-l", "9", "-nopgbrk", doc.path, "-"],
                text=True,
            )

        txt = unidecode(txt)

        txt = txt.split("\n\n")
        for i in range(len(txt) - 1, -1, -1):
            txt[i] = txt[i].lstrip().replace("\n", " ")
            if len(txt[i]) < 10:
                del txt[i]
        txt = "\n\n".join(txt)

        doc["txt"] = txt[:20000]
        return

    def check_doi(doc):
        if doc["type"] == "arxiv":
            html = BeautifulSoup(
                Get("https://arxiv.org/abs/" + doc["ref"]).text,
                features="xml",
            )
            doi_refs = html.select('meta[name="citation_doi"]')
            if doi_refs:
                for doi_ref in doi_refs:
                    r = doi_ref.get("content")
                    if "arXiv" not in r:
                        return r
        return

    def make_ocr(doc):
        ocr(
            doc.path,
            doc.path,
            language=["eng", "fra"],
            output_type="pdfa",
            jobs=4,
            rotate_pages=True,
            deskew=True,
            force_ocr=True,
            skip_big=20,
        )
        return


def format_bib(inp):
    inp = totex(inp)
    bib_format = (
        (module_dir / "etc" / "bib_format.txt").read_text().splitlines()
    )
    return sp.check_output(bib_format, input=inp, text=True)


def totex(inp):
    rewrite_rules = (
        (module_dir / "etc" / "rewrite_rule.txt").read_text().splitlines()
    )
    return sp.check_output(rewrite_rules, input=inp, text=True)
