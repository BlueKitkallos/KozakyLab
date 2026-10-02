GAMES = {
    'AYG': ('nt', 'Yu-Gi-Oh! Nightmare Troubadour'),
    'AYX': ('sc', 'Yu-Gi-Oh! GX Spirit Caller'),
    'AY7': ('wc2007', 'Yu-Gi-Oh! World Championship 2007'),
    'YG8': ('wc2008', 'Yu-Gi-Oh! World Championship 2008'),
    'CY8': ('wc2009', "Yu-Gi-Oh! 5D's Stardust Accelerator: World Championship 2009"),
    'BYX': ('wc2010', "Yu-Gi-Oh! 5D's World Championship 2010: Reverse of Arcadia"),
    'BYY': ('wc2011', "Yu-Gi-Oh! 5D's World Championship 2011: Over the Nexus"),
}

REGIONS = {'J': 'Japan', 'E': 'USA', 'P': 'Europe', 'K': 'Korea'}

KNOWN_DUMPS = {
    '454cd23c65d830df9c0f8d560755e86e717f39d7': 'AY7E',
    'c300fe82ae4039cc05c2ea3e872272524089dbae': 'AY7J',
    'b4176e75eff0df30b95899be627fc7ecab7727e4': 'AY7P',
    'dde5eb8add6ecb78bc2d5eef3cb576e598885ea4': 'AY7P',
    '64d34892bc27e8ba69f7cf9213bd6be0faa0295c': 'AYGE',
    '88ef970d178d6030436f8c48acebb24c23a2e805': 'AYGE',
    '581ddab1dad531c3eef0ff01d82dca6a71112ece': 'AYGJ',
    '328c6dc576a450aba8dcc8bdb7de222291ee16a6': 'AYGP',
    '34e60dfa20509f80596e2d622d6e2cb95e616939': 'AYGP',
    '9e53dcc74d8a9db4de6b655d62a1da6f5e9c2a83': 'AYXE',
    '761fbfc62f4fe74f867e973a5eda91b8e86424f6': 'AYXJ',
    '1da50df7c210fae96dc69b3825554b9ce13b4f75': 'AYXP',
    'cdd10b8301e4a146ecaa717dbdb10f593f2487eb': 'AYXP',
    '2d21739de0503ff44c63bf88cef9c98b38acdb24': 'BYXE',
    'cab9ea8f43aa14255b4e1f553dde84aa86fb2949': 'BYXE',
    '8745cf1e7a16c28ff5c99b510e2b9908ba9e1f3b': 'BYXJ',
    '215566ce5ba8a6fc29c8788b7bce479bb5e19465': 'BYXK',
    '8e8c6780e45cbca27aa38d116b9647be76a14271': 'BYXP',
    '82393654b262b279386499af2906e733b0150553': 'BYYE',
    '16d077e4a2d48bfac748530555b7ead06c85d221': 'BYYJ',
    '3cac56b2156031cc9aaa6cfdbe62af2f05b4d215': 'BYYK',
    '7617788d197ffd45d2ab2bb6deadbf0f9874e2fa': 'BYYP',
    'e88f5398af8676f4e48d4aaa42ee17dd763a15b6': 'BYYP',
    '4f2e17ddf5d438f3e8ef3bd0cc11cbab6a2d871e': 'CY8E',
    'da5f94ae86bebabda700d16e28cf3297fb16fe9b': 'CY8E',
    '7475680b13442a678911feb6cfe205c1f7b86726': 'CY8J',
    '41f2191b110bed0505db2e5d55071f6a63be097a': 'CY8K',
    '700ba4d826c3fbfac1cea25250e6e8f231f31c75': 'CY8K',
    '84f41230b4b7e78821c9a38622f028adeff959ef': 'CY8P',
    '9f9931e7ad01724f4478881626580f0d45fd08e5': 'YG8E',
    'bd3b836b2758fdaf3db1759c622f387ee0c407f2': 'YG8E',
    '7ea139a207cb5899e3c51e24d01ac8a059c27ccd': 'YG8J',
    'a08c5d96745adcf64db538002282e3eed739ac34': 'YG8J',
    '1b5ad981bafbb04130f3a676b23bbcf6c69e383f': 'YG8K',
    '6964f169c8af4c77432f15f2024bf75ebae95daa': 'YG8P',
    '86c0d2b17bcd13c6ad5d923bb8fdba5a54298083': 'YG8P',
}


def identify(code):
    game = GAMES.get(code[:3])
    return {
        'game': game[0] if game else None,
        'name': game[1] if game else 'unsupported game',
        'region': REGIONS.get(code[3:4], f'region {code[3:4]!r}'),
        'code': code,
    }


def describe(code, version):
    g = identify(code)
    return f"{g['name']} ({g['region']}, {code}, revision {version})"


def supported(code):
    return code[:3] in GAMES and code[3:4] in REGIONS
