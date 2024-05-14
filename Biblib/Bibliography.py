import requests
import json
import subprocess as sp
import pyperclip as clip

from sys import exit
from os import getenv
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .Document import Document, format_bib

module_dir = Path(__file__).parent

HOME = Path(getenv("HOME"))
BIB = getenv("BIB", str(HOME / ".bib"))
PDF = getenv("PDF", "xdg-open")


def tostring(tags):
    return ", ".join(tags)


def parse(tags):
    if not tags:
        return []
    return [tag.strip() for tag in tags.split(",")]


class Bibliography(dict):
    def __init__(bib, opts):
        bib.opts = opts
        di = Path(BIB)
        di.mkdir(parents=True, exist_ok=True)
        fl = di / "bib.json"

        if fl.is_file():
            ini_bib = json.loads(fl.read_text())
        else:
            ini_bib = {}

        super().__init__(ini_bib)

        for ref, doc in bib.items():
            bib[ref] = Document(doc)

        bib.dir = di
        bib.file = fl
        bib.bibtex = bib.dir / "bib.bib"

        bib.types = ("doi", "isbn", "arxiv")
        return

    def delete(bib, ref):
        bib[ref].path.unlink()
        bib[ref].mess("deleting...")
        del bib[ref]
        bib.update()
        return

    def open(bib, refs):
        paths = set()
        for ref in refs:
            paths.add(bib[ref].path)
        sp.Popen([PDF, "--fork", *paths])

    def copy(bib, refs):
        for ref in refs:
            fl = bib[ref].path
            new_file = fl.relative_to(bib.dir / bib[ref]["type"]).name
            new_path = HOME / new_file
            new_path.parent.mkdir(parents=True, exist_ok=True)
            new_path.write_bytes(fl.read_bytes())

    def update(bib):
        if bib.file.is_file():
            bib.file.unlink()
        tmp_dict = {
            ref: {prop: val for prop, val in doc.items()}
            for ref, doc in bib.items()
        }
        bib.file.write_text(json.dumps(tmp_dict))
        bib.make_bib()
        return

    def make_bib(bib):
        biblio = []
        for ref in bib.keys():
            biblio.append(bib[ref]["bib"])
        biblio = "\n\n".join(biblio)
        biblio = format_bib(biblio)
        with bib.bibtex.open("w") as f:
            f.write(biblio)
        return

    def add(bib, tp, ref, what=("doc", "bib", "txt"), **kwargs):
        kwargs["tags"] = kwargs.get("tags", [])
        kwargs["tags"] = list(set(kwargs["tags"] + parse(bib.opts.tags)))
        kwargs["alternate_bib"] = bib.opts.alternate_bib
        kwargs["file"] = bib.opts.file

        def makedoc():
            doc = Document({"BIB": BIB, "type": tp, "ref": ref, **kwargs})
            for thing in what:
                doc.get(thing)
            return doc

        ref = ref.lower()
        if tp == "isbn":
            ref = ref.replace("-", "")

        full_ref = f"{tp}/{ref}"

        if bib.get(full_ref):
            if bib.opts.replace:
                bib[full_ref] = makedoc()
            else:
                bib[full_ref]["tags"] = list(
                    set(bib[full_ref]["tags"] + kwargs["tags"])
                )
        else:
            bib[full_ref] = makedoc()

        if bib.opts.force_ocr:
            bib[full_ref].make_ocr()
            bib[full_ref].get_txt()

        return full_ref

    def scan(bib):
        for tp in bib.types:
            di = bib.dir / tp
            for ftp in ["pdf", "epub", "djvu"]:
                for f in di.rglob("*." + ftp):
                    ref = f.relative_to(di).with_suffix("")
                    if not bib.get(str(tp / ref)):
                        bib.add(
                            tp, str(ref), what=("bib", "txt"), ext=f.suffix
                        )
                        bib.update()
        return

    def convert(bib):
        keys = list(bib.keys()).copy()
        for ref in keys:
            doi = bib[ref].check_doi()
            if doi is not None and "HIDDEN" not in bib[ref]["tags"]:
                print(f"Converting {ref} to DOI {doi}")
                bib.add("doi", doi, tags=bib[ref]["tags"])
                bib[ref]["tags"].append("HIDDEN")
        return

    def fetch(bib):
        searches = json.loads(
            (module_dir / "etc" / "arxiv_scrape.json").read_text()
        )

        for search in searches:
            queries = search.pop("queries")
            cats = search.pop("categories", [])
            tags = search.pop("tags", ["SCRAPED"])

            refs = set()
            refs.update(arxiv_query(queries, cats, **search))
            breakpoint()
            for ref in refs:
                bib.add("arxiv", ref, tags=tags)
        return

    def show(bib):
        controls = {
            "enter": "",
            "ctrl-v": "V: Copy ~",
            "ctrl-b": "B: .bib",
            "ctrl-o": "O: OCR",
            "ctrl-x": "X: TeXt",
            "ctrl-t": "T: Tags",
            "ctrl-d": "D: Doc",
            "ctrl-k": "K: Hide",
            "ctrl-h": "H: Show H",
            "ctrl-p": "P: Delete",
        }

        query = ""
        while 1:
            txts = []
            for ref in bib.keys():
                if bib.opts.show_hidden or "HIDDEN" not in bib[ref]["tags"]:
                    tags = ", ".join(bib[ref]["tags"])
                    if not tags:
                        tags = "NOTAGS"
                    txts.append(f'{ref}\n{tags}\n{bib[ref]["txt"]}')

            query, key, refs = FZF(txts, controls, query)

            if not key:
                break

            elif "enter" in key:
                bib.open(refs)

            elif "ctrl-h" in key:
                bib.opts.show_hidden = not bib.opts.show_hidden

            elif "ctrl-k" in key:
                for ref in refs:
                    bib[ref].toggle()

            elif "ctrl-v" in key:
                bib.copy(refs)

            elif "ctrl-b" in key:
                bib_entries = []
                for ref in refs:
                    bib_entries.append(bib[ref]["bib"])

                bib_entries = "\n\n".join(bib_entries)
                print(bib_entries)
                clip.copy(bib_entries)

            elif "ctrl-o" in key:
                for ref in refs:
                    bib[ref].make_ocr()

            elif "ctrl-d" in key:
                for ref in refs:
                    bib[ref].get("doc")
                    bib[ref].get("txt")

            elif "ctrl-x" in key:
                for ref in refs:
                    bib[ref].get("txt")

            elif "ctrl-p" in key:
                for ref in refs:
                    bib.delete(ref)

            elif "ctrl-t" in key:
                opts = set()
                for ref in refs:
                    if len(bib[ref]["tags"]):
                        opts.add(tostring(bib[ref]["tags"]))

                query = opts.pop() if opts else ""
                new_tags, key, _ = FZF(opts, query=query)

                for ref in refs:
                    bib[ref]["tags"] = parse(new_tags)
        return


def arxiv_query(queries, categories, **kwargs):
    url = "http://export.arxiv.org/api/query"

    searches = [f"( {q} )" for q in queries]
    searches = [" OR ".join(searches)]

    cats = [f"( {c} )" for c in categories]
    if cats:
        cats = [" OR ".join(cats)]

    search_query = " AND ".join(searches + cats)

    kwargs = {
        "search_query": search_query,
        "start": "0",
        "max_results": "10",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        **kwargs,
    }

    xml = requests.get(url, params=kwargs).content
    xml = BeautifulSoup(xml, "lxml-xml")
    articles = xml.find_all("entry")

    refs = set()
    for article in articles:
        refs.add(get_arxiv_ref(article))
    return refs


def get_arxiv_ref(link):
    link = link.find("id").get_text()
    if link.startswith("http"):
        link = str(urlparse(link).path)
        if link.startswith("/abs/"):
            link = link[5:]
    return link


def FZF(inp, keys, query):
    inp = "\0".join(inp)
    prog = [
        "fzf",
        "--read0",
        "--print0",
        "-e",
        "-m",
        "--expect",
        ",".join(keys.keys()),
        "--header",
        "  ".join(keys.values()),
        "--preview-window",
        "nohidden:80%",
        "--print-query",
        "-q",
        query,
        "--preview",
        r"""
            v=$(echo {q} | tr " " "|")
        echo {} |
        grep -a -E "^|$v" -i --color=always | fold -s -w $(echo "$COLUMNS-5" | bc)
        """,
    ]
    try:
        out = (
            sp.check_output(prog, input=inp, text=True)
            .rstrip("\0")
            .split("\0")
        )
    except sp.CalledProcessError:
        return None, None, None
    query, key, vals = out[0], out[1], out[2:]
    vals = [v.splitlines()[0] for v in vals]
    return query, key, vals
