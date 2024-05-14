
# Bibliographic manager

A python script to manage a local bibliographic repository.

* Each document is added through its DOI/ARXIV/ISBN reference number.
* Documents obtained from LibGen, .bib entries automatically downloaded.
* Search through entire library on text scraped from pdfs.
* Tag documents with keywords for easier search.

[Turing.webm](https://github.com/ivomac/bib/assets/45886067/c9e45b54-41ad-4c52-8146-754def098eb8)

In the video we:

* add [this paper](https://londmathsoc.onlinelibrary.wiley.com/doi/abs/10.1112/plms/s2-42.1.230) using its DOI code
* tag it (`-t`) while adding it
* then search for it and open it with the default pdf viewer.

## Requirements

* Python3

    * ocrmypdf
    * coloredlogs
    * pyperclip
    * bs4
    * reportlab
    * unidecode
    * json

* [fzf](https://github.com/junegunn/fzf)

* [bibtool](http://www.gerd-neugebauer.de/software/TeX/BibTool/en/)

* bc

## Commands


* add - add document to library by DOI, arxiv ref, or ISBN.
* show - search the library (See Show Controls).
* scan - add unreferenced documents in library folder to library.
* fetch - scrape arxiv for new (or old) articles (See ArXiv Scraping).
* convert - update arxiv docs to DOI if DOI available.

## Show Controls

* Press TAB to select several documents
* Enter: open selected file(s)
* ctrl-b: Print bibtex entries and copy them to clipboard
* ctrl-d: Get doc
* ctrl-h: Show hidden documents (tagged with HIDDEN)
* ctrl-k: Toggle HIDDEN tag
* ctrl-o: Redo OCR
* ctrl-p: Delete from library
* ctrl-t: Edit Tags
* ctrl-v: Copy to home folder
* ctrl-x: Redo text extraction from pdf

## ArXiv Scraping

The config for the arxiv scraping (`bib fetch`) is found in `arxiv_scrape.json`. The entries follow the format of the example:

        {
            "queries": ["all:openai AND all:chatgpt", "ti:singularity"],
                                            // all:all, ti:title
            "categories": ["cat:cs.AI AND cat:cs.IT", "cat:cs.LG"],
                                            // list[0] OR list[1]
            "start": "10",                  // default: 0
            "max_results": "5",             // default: 15
            "sortOrder": "descending",      // default: "descending"
            "sortBy": "lastUpdatedDate",    // default: "submittedDate"
            "tags": ["THE_END_IS_NIGH"]     // default: ["SCRAPED"]
        },

Available categories are found [here](https://arxiv.org/category_taxonomy).

## Config

By default, the library is saved in the folder specified by the `$BIB` environment variable.

Docs are opened with `$PDF` or `xdg-open`.

