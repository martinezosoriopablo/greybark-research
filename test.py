
import feedparser

feeds = {
    # Política específica
    'El Tiempo Política': 'https://www.eltiempo.com/rss/politica.xml',
    'Caracol Política': 'https://www.caracol.com.co/rss/actualidad/politica/',
    'RCN Política': 'https://www.rcnradio.com/politica/feed',
    'W Radio Colombia': 'https://www.wradio.com.co/rss/colombia.xml',
    'Pulzo Nación': 'https://www.pulzo.com/rss/nacion',
    'La Silla Vacía': 'https://www.lasillavacia.com/rss.xml',
    'Razón Pública': 'https://razonpublica.com/feed/',
    'Cambio Colombia': 'https://cambiocolombia.com/feed',
    'Las 2 Orillas': 'https://www.las2orillas.co/feed/',
    'Infobae Colombia': 'https://www.infobae.com/feeds/rss/colombia/',
    'Blu Radio': 'https://www.bluradio.com/rss',
    'Noticias Caracol': 'https://www.noticiascaracol.com/rss',
    'Revista Semana': 'https://www.semana.com/rss',
    'Congreso Visible': 'https://congresovisible.uniandes.edu.co/rss/',
}

total = 0
working = []
for name, url in feeds.items():
    try:
        f = feedparser.parse(url)
        count = len(f.entries)
        status = '✓' if count > 0 else '✗'
        print(f'{status} {name}: {count}')
        if count > 0:
            total += count
            working.append((name, url, count))
    except Exception as e:
        print(f'✗ {name}: Error')

print(f'\\n--- TOTAL: {total} artículos de {len(working)} fuentes ---')
"