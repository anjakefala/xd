#!/usr/bin/env python3

from collections import Counter
import re

from xdfile.utils import progress, open_output, get_args, args_parser, COLUMN_SEPARATOR
from xdfile import html, utils, catalog, pubyear
from xdfile import metadatabase as metadb
import xdfile


class PublicationStats:
    def __init__(self, pubid):
        self.pubid = pubid
        self.copyrights = Counter()  # [copyright_text] -> number of xd
        self.editors = Counter()  # [editor_name] -> number of xd
        self.formats = Counter()  # ["15x15 RS"] -> number of xd
        self.mindate = ""
        self.maxdate = ""
        self.num_xd = 0

        self.puzzles_meta = []

    def add(self, puzrow):
        self.copyrights[puzrow.Copyright.strip()] += 1
        self.editors[puzrow.Editor.strip()] += 1
        self.formats[puzrow.Size] += 1
        datestr = puzrow.Date
        if datestr:
            if not self.mindate:
                self.mindate = datestr
            else:
                self.mindate = min(self.mindate, datestr)
            if not self.maxdate:
                self.maxdate = datestr
            else:
                self.maxdate = max(self.maxdate, datestr)
        self.num_xd += 1

        self.puzzles_meta.append(puzrow)

    def meta(self):
        return 'pubid num dates formats copyrights editors'.split()

    def row(self):
        return [
                self.pubid,
                html.mkhref(str(self.num_xd), self.pubid),
                "%s &mdash; %s" % (self.mindate, self.maxdate),
                html_select_options(self.formats),
                html_select_options(self.copyrights),
                html_select_options(self.editors),
               ]


def tally_to_cell(d):
    freq_sorted = sorted([(v, k) for k, v in list(d.items())], reverse=True)

    if not freq_sorted:
        return ""
    elif len(freq_sorted) == 1:
        return "<br>".join("%s [x%s]" % (k, v) for v, k in freq_sorted)
    else:
        return "<select><option>" + "</option><option>".join("%s [x%s]" % (k, v) for v, k in freq_sorted) + "</select>"


def publication_header():
    return "PubId NumCollected DatesCollected Formats Copyrights Editors".split()


def main():
    parser = args_parser("generate publishers index html pages and index")

    args = get_args(parser=parser)

    outf = open_output()

    all_pubs = {}  # [(pubid,year)] -> PublicationStats

    pubyear_rows = {}

    similar = metadb.xd_similar()
    puzzles = metadb.xd_puzzles()

    outf.write_html('pub/index.html', pubyear.pubyear_html(), title='The xd crossword puzzle corpus')

    utils.log("collating puzzles")
    for puzrow in puzzles.values():
            pubid = utils.parse_pubid(puzrow.xdid)
            year = xdfile.year_from_date(puzrow.Date)
            k = (pubid, year or 9999)
            if k not in all_pubs:
                all_pubs[k] = PublicationStats(pubid)

            pubyear_rows[pubid] = []

            all_pubs[k].add(puzrow)


    pubyear_header = [ 'xdid', 'Date', 'Size', 'Title', 'Author', 'Editor', 'Copyright', 'Grid_1A_1D', 'ReusedCluePct', 'SimilarGrids' ]
    utils.log('generating index pages')
    for pair, pub in sorted(list(all_pubs.items())):
        pubid, year = pair
        progress(pubid)
   
        reused_clues = 0
        reused_answers = 0
        total_clues = 0
        total_similar = []

        rows = []
        for r in pub.puzzles_meta:
            similar_text = ""
            reused_clue_pct = "n/a"

            rsim = similar.get(r.xdid)
            if rsim:
                similar_pct = float(rsim.similar_grid_pct)
                if similar_pct > 0:
                    matches = [x.split('=') for x in rsim.matches.split()]
                    for xdid, pct in matches:
                        similar_text += '(%s%%) %s [%s]<br/>' % (pct, puzzles[xdid].Author, xdid)
                    total_similar.append(similar_pct)
                else:
                    similar_text = "0"

                reused_clues += int(rsim.reused_clues)
                reused_answers += int(rsim.reused_answers)
                total_clues += int(rsim.total_clues)

                reused_clue_pct = int(100*(float(rsim.reused_clues) / float(rsim.total_clues)))

            if similar_text and similar_text != "0":
                pubidtext = html.mkhref(r.xdid, '/pub/' + r.xdid)
            else:
                pubidtext = r.xdid

            row = [ 
                pubidtext,
                r.Date,
                r.Size,
                r.Title,
                r.Author,
                r.Editor,
                r.Copyright,
                r.A1_D1,
                reused_clue_pct,
                similar_text
              ]

            outf.write_row('pub/%s%s.tsv' % (pubid, year), " ".join(pubyear_header), row)
            rows.append(row)

        onepubyear_html = pubyear.pubyear_html([(pubid, year, len(rows))])
        onepubyear_html += html.html_table(sorted(rows, key=lambda r: r[1]), pubyear_header, "puzzle")
        outf.write_html("pub/%s%s/index.html" % (pubid, year), onepubyear_html, title="%s %s" % (pubid, year))
       
        cluepct = ""
        wordpct = ""
        if total_clues:
            cluepct = "%d%%" % int(100.0*(total_clues-reused_clues)/total_clues)
            wordpct = "%.2f%%" % int(100.0*(total_clues-reused_answers)/total_clues)

        pubyear_rows[pubid].append([
            pubid,
            str(year),
            len(rows),
            "%.2f/%d" % (sum(total_similar)/100.0, len(total_similar)),
            wordpct,
            cluepct
            ])

    pub_header = "Year NumberOfPuzzles SimilarPuzzles OriginalWordPct OriginalCluePct".split()            

    for pubid, tsvrows in list(pubyear_rows.items()):
        rows = []
        for pubid, y, n, similarity, wordpct, cluepct in tsvrows:
            pubhref = html.mkhref(str(y), '/pub/%s%s' % (pubid, y))
            rows.append((pubhref, n, similarity, wordpct, cluepct))
        pub_h = html.html_table(sorted(rows), pub_header, "onepub")
        outf.write_html("pub/%s/index.html" % pubid, pub_h, title="%s" % pubid)

    progress()


if __name__ == "__main__":
    main()
