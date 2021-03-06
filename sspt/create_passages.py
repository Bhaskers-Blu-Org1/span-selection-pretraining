import regex as re
from util.line_corpus import expand_files, read_lines
import argparse
import json
import gzip
import numpy as np
import math
from util.reporting import Reporting
import logging
import time
import os
import unicodedata

logging.basicConfig(format='%(filename)s:%(lineno)d - %(message)s',
                    datefmt='%m/%d/%Y %H:%M:%S',
                    level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """
    input format: {"id": "", "revid": "", "url":"", "title": "", "text": "..."}
    output format: {"id": "", "contents": ""}
    both jsonl
    :return:
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("--wikiextracted", default=None, type=str, required=True,
                        help="The input data dir. Should contain the json output of WikiExtractor.py.")
    parser.add_argument("--output", default=None, type=str, required=True,
                        help="The output directory.")
    parser.add_argument("--min_length", default=50, type=int,
                        help="Minimum number of characters for a paragraph.")
    parser.add_argument("--max_length", default=2000, type=int,
                        help="Maximum number of characters for a paragraph.")
    parser.add_argument("--target_passage_length", default=300, type=int,
                        help="Target number of characters for a passage. Set to zero to split by paragraph.")
    parser.add_argument("--max_newlines", default=7, type=int,
                        help="Maximum number of newlines in a passage.")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    paras_per_file = 100000
    out = None
    file_count = 0
    file_doc_count = 0
    report = Reporting()
    length_counts = np.zeros(20, dtype=np.int32)
    para_split = re.compile(r"""\s*\n\s*\n\s*""")
    for line in read_lines(expand_files(args.wikiextracted, '*')):
        if report.is_time():
            report.display()
            logger.info(f'On document {report.check_count}, '
                        f'{report.check_count/(time.time()-report.start_time)} documents per second')
        jobj = json.loads(line)
        text = jobj['text'].strip()

        # strip unicode combos
        text = unicodedata.normalize('NFKD', text)
        text = ''.join([c for c in text if not unicodedata.combining(c)])

        paragraphs = re.split(para_split, text)
        # CONSIDER: docstride?
        current_passage = ''
        passage_count = 0
        for paragraph in paragraphs:
            plen = len(paragraph)
            if plen > args.max_length:
                current_passage = ''
                continue
            if not current_passage and plen < args.min_length:
                continue
            current_passage += paragraph + '\n\n'
            if len(current_passage) >= args.target_passage_length:
                current_passage = current_passage.strip()
                if current_passage.count('\n') <= 7:
                    # track distribution of passage length
                    lndx = int(math.log2(len(current_passage)))
                    if lndx >= length_counts.shape[0]:
                        lndx = length_counts.shape[0] - 1
                    length_counts[lndx] += 1
                    passage_count += 1
                    # build passage document
                    adoc = dict()
                    adoc['id'] = jobj['id']
                    adoc['contents'] = current_passage
                    # write to file
                    if file_doc_count >= paras_per_file:
                        out.close()
                        out = None
                        file_doc_count = 0
                    if out is None:
                        out = gzip.open(f'{args.output}/{file_count}.jsonl.gz', 'wt', encoding='utf-8')
                        file_count += 1
                    out.write(json.dumps(adoc)+'\n')
                    file_doc_count += 1
                current_passage = ''
        report.moving_averages(paragraphs_per_doc=len(paragraphs), passages_per_doc=passage_count)
    if out is not None:
        out.close()
    # display length counts
    for i in range(length_counts.shape[0]):
        if length_counts[i] == 0:
            continue
        logger.info(f'Passage length {int(math.pow(2, i))}-{int(math.pow(2,i+1))-1}: {length_counts[i]}')


if __name__ == "__main__":
    main()
