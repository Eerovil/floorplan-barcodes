from sqlitedict import SqliteDict
import os
import requests
import sys

data_folder = '/data'
if not os.path.exists(data_folder):
    data_folder = '../data'

import logging
logger = logging.getLogger(__name__)
streamHandler = logging.StreamHandler(sys.stdout)
logger.addHandler(streamHandler)
logger.setLevel(logging.DEBUG)

logger.info("starting")


pokemons_table = SqliteDict(os.path.join(data_folder, 'pokemons.db'), tablename="pokemons", autocommit=True)

def table_setter(pokemon_key, key, value):
    pokemon = pokemons_table[pokemon_key]
    pokemon[key] = value
    logger.info("setting %s %s to %s", pokemon_key, key, value)
    pokemons_table[pokemon_key] = pokemon


if len(list(pokemons_table.keys())) == 0:
    resp = requests.get('https://pokeapi.co/api/v2/pokemon?limit=151')
    pokemons = resp.json()['results']
    for result in pokemons:
        pokemons_table[result['name']] = {
            'slug': result['name'],
            'api_url': result['url'],
        }

    logger.info('Fetched {} pokemons'.format(len(list(pokemons_table.keys()))))


for name, values in pokemons_table.items():
    if 'animated' in values:
        logger.info("Skipping {}".format(name))
        continue
    logger.info("Fetching {}".format(name))
    # Fetch the pokemon
    resp = requests.get(values['api_url'].replace('pokemon-species', 'pokemon'))
    pokemon = resp.json()
    # save sprites
    try:
        animated = pokemon['sprites']['versions']['generation-v']['black-white']['animated']
        values['animated'] = animated
    except KeyError:
        logger.info('No animated sprite for {}'.format(name))
        import ipdb; ipdb.set_trace()

    try:
        dream_world = pokemon['sprites']['other']['dream_world']
        values['dream_world'] = dream_world
    except KeyError:
        logger.info('No dream_world sprite for {}'.format(name))

    logger.info("Saved {}".format(name))
    pokemons_table[name] = values


# Download images
if False:
    for name, values in pokemons_table.items():

        animated = values.get('animated', {})
        dream_world = values.get('dream_world', {})

        def _download(folder, image_dict):
            # Download the images, with keys as filenames and value as url
            # detect file extension from value
            for key, value in image_dict.items():
                # Skip downloading if the file already exists
                if value is None:
                    continue
                ext = value.split('.')[-1]
                if os.path.exists(os.path.join(data_folder, folder, key)):
                    continue
                resp = requests.get(value)
                with open(os.path.join(folder, '{}.{}'.format(key, ext)), 'wb') as f:
                    f.write(resp.content)

        os.makedirs(os.path.join(data_folder, name), exist_ok=True)
        os.makedirs(os.path.join(data_folder, name, 'animated'), exist_ok=True)
        _download(os.path.join(data_folder, name, 'animated'), animated)
        os.makedirs(os.path.join(data_folder, name, 'dream_world'), exist_ok=True)
        _download(os.path.join(data_folder, name, 'dream_world'), dream_world)
        logger.info("Saved images for {}".format(name))


# Fetch evolution chains
missing = False
for name, values in pokemons_table.items():
    if 'evolution' not in values:
        logger.info("Missing evolution for {}".format(name))
        missing = True

if missing:
    i = 0
    while i < 1000:
        i += 1
        resp = requests.get('https://pokeapi.co/api/v2/evolution-chain/{}'.format(i))
        if resp.status_code == 404:
            break
        try:
            evolution_chain = resp.json()
            try:
                chain = evolution_chain['chain']
                first_pokemon = chain['species']['name']
                second_chain = chain['evolves_to'][0]
                second_pokemon = second_chain['species']['name']
                if first_pokemon not in pokemons_table:
                    if second_pokemon in pokemons_table:
                        pokemons_table[first_pokemon] = {
                            'slug': first_pokemon,
                            'api_url': chain['species']['url']
                        }
                    else:
                        break
            except (KeyError, IndexError):
                logger.info("0 evolutions for {}".format(first_pokemon))
                table_setter(first_pokemon, 'evolution', None)
                continue

            if second_pokemon not in pokemons_table:
                continue

            try:
                table_setter(first_pokemon, 'evolution', second_pokemon)
                third_chain = second_chain['evolves_to'][0]
                third_pokemon = third_chain['species']['name']
            except (KeyError, IndexError):
                logger.info("1 evolutions for {}".format(first_pokemon))
                continue

            if third_pokemon not in pokemons_table:
                continue

            try:
                table_setter(second_pokemon, 'evolution', third_pokemon)
                fourth_chain = third_chain['evolves_to'][0]
                fourth_pokemon = fourth_chain['species']['name']
            except (KeyError, IndexError):
                logger.info("2 evolutions for {}".format(first_pokemon))
                continue

            if fourth_pokemon not in pokemons_table:
                continue

            table_setter(third_pokemon, 'evolution', fourth_pokemon)

            logger.info('Saved evolution chain for {}'.format(first_pokemon))

        except Exception:
            import ipdb; ipdb.set_trace()





import ipdb; ipdb.set_trace()

