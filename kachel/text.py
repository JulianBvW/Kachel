'''Text the way searching compares it. Shared by the app and file search.'''

import unicodedata


def normalize(text):
    '''Lower case and without accents: 'Écran' and 'ecran' are the same.'''
    decomposed = unicodedata.normalize('NFKD', (text or '').casefold())
    return ''.join(c for c in decomposed if not unicodedata.combining(c))
