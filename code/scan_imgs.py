from sqlitedict import SqliteDict
import os
import sys
import glob


data_folder = '/data'
if not os.path.exists(data_folder):
    data_folder = '../data'

import logging
logger = logging.getLogger(__name__)
streamHandler = logging.StreamHandler(sys.stdout)
logger.addHandler(streamHandler)
logger.setLevel(logging.DEBUG)

logger.info("starting")

os.unlink(os.path.join(data_folder, 'img_animals.db'))

img_animals_table = SqliteDict(os.path.join(data_folder, 'img_animals.db'), tablename="img_animals", autocommit=True)

for pathname in glob.glob(data_folder + '/img_animals/*'):
    filename = 'img_animals/' + os.path.basename(pathname)
    logger.info("Fetching {}".format(filename))

    img_animals_table[filename] = {
        'slug': filename,
    }
