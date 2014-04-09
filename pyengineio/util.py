import urllib


def qs(d):
    result = ''

    for key, value in d.items():
        if result:
            result += '&'

        result += urllib.quote(key) + '=' + urllib.quote(d[key])

    return result


def qs_parse(qs):
    qry = {}

    pairs = [p.split('=') for p in qs.split('&')]
    for pair in pairs:
        if not pair:
            continue

        value = urllib.unquote(pair[1]) if len(pair) == 2 else None

        qry[urllib.unquote(pair[0])] = value

    return qry