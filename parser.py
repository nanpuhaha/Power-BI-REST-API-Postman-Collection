import json
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = 'https://docs.microsoft.com/en-us/rest/api/power-bi/'


def parse_page(soup, url):
    query, body = [], {}

    uri_parameters_table = soup.select_one('#uri-parameters + table')
    if uri_parameters_table:
        trs = uri_parameters_table.select('tr')

        name_index, in_index, required_index, type_index, description_index = 0, 1, 2, 3, 4

        for tr in trs:
            if ths := tr.select('th'):
                columns = [th.text.strip() for th in ths]
                print("URI Parameters:", columns)
                # Name	In	Required	Type	Description
                name_index = columns.index('Name')
                in_index = columns.index('In')
                required_index = columns.index('Required')
                type_index = columns.index('Type')
                description_index = columns.index('Description')

            elif tds := tr.select('td'):
                row = [re.sub(r'( )+', ' ', td.text.strip().replace('\r', ' ').replace('\t', ' ').replace('\n', ' ')) for td in tds]
                if row[in_index] == 'path':
                    continue
                else:   # query
                    name = row[name_index]
                    required = row[required_index]
                    data_type = row[type_index]
                    description = row[description_index]
                    optional = '(Optional) ' if not required else ''
                    query.append({
                        'key': name,
                        'value': None,
                        'description': f"{data_type} {optional}{description}",
                        'disabled': True if not required else False
                    })
            else:
                print(f"ELSE ?!?!?!?!")
                raise

    items = [f"{item['key']}={item['value']}" for item in query]
    if items:
        url += '?' + '&'.join(items)

    request_body_table = soup.select_one('#request-body + table')
    if request_body_table:
        body['mode'] = 'raw'
        body['raw'] = ''
        body_raw_dict = {}
        trs = request_body_table.select('tr')

        name_index, required_index, type_index, description_index = 0, 1, 2, 3

        for tr in trs:
            if ths := tr.select('th'):
                columns = [th.text.strip() for th in ths]
                print("Request Body:", columns)

                name_index = columns.index('Name')
                type_index = columns.index('Type')
                description_index = columns.index('Description')
                try:
                    required_index = columns.index('Required')
                except ValueError:
                    required_index = -1
                    pass

            elif tds := tr.select('td'):
                row = [td.text.strip() for td in tds]
                body_raw_dict[row[name_index]] = ''
            else:
                print(f"ELSE ?!?!?!?!")
                raise

        body['raw'] = json.dumps(body_raw_dict, indent='\t')

    return query, body, url


def main():

    # ------------------------------------------------------------------------
    #                   0. Postman Collection v2.1 뼈대
    # ------------------------------------------------------------------------

    postman_collection = {
        "info": {
            "name": "Power BI REST API v1",
            "description": "Power BI REST API provides service endpoints for embedding, administration, and user resources.\r\n\r\nhttps://docs.microsoft.com/en-us/rest/api/power-bi/",
            "version": {
                "major": 0,
                "minor": 1,
                "patch": 0,
                "identifier": f"beta-{datetime.now().strftime('%y%m%d')}",
                "meta": "Jangwon Seo"
            },
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": [],
        "protocolProfileBehavior": {}
    }

    # ------------------------------------------------------------------------
    #             1. 제일 큰 구조   (REST Operation groups → Folder)
    # ------------------------------------------------------------------------
    time.sleep(1)
    r = requests.get(BASE_URL)
    # soup = BeautifulSoup(r.content.decode(), 'lxml')
    soup = BeautifulSoup(r.content.decode(), 'html.parser')
    table = soup.select_one('table')
    tbody = table.select_one('tbody')
    trs = tbody.select('tr')

    lis = []
    for tr in trs:
        title = tr.select_one('td:nth-child(1) > a').text.strip()
        link = tr.select_one('td:nth-child(1) > a').get('href')
        description = tr.select_one('td:nth-child(2)').text.strip()
        lis.append({
            'name': title,
            'item': [],
            'description': description + '\r\n\r\n' + link,
            'protocolProfileBehavior': {},
            '_link': BASE_URL + link
        })

    # ------------------------------------------------------------------------
    #         2. REST Operation groups 각각의 Operations → Request
    # ------------------------------------------------------------------------
    for i, li in enumerate(lis):
        print(f"[{i+1:2}/{len(lis)}] {li['name']}")
        time.sleep(1)
        r = requests.get(li['_link'])
        soup = BeautifulSoup(r.content.decode(), 'html.parser')
        table = soup.select_one('table')
        trs = table.select('tr')

        operations = []
        for tr in trs:
            a = tr.select_one('td:nth-child(1) > a')
            name = a.text.strip()
            full_href = urljoin(BASE_URL, a.get('href'))
            description_title = f"<a href='{full_href}'>{name}</a>"
            description_html = tr.select_one('td:nth-child(2)').decode_contents().strip()

            time.sleep(1)
            inner_r = requests.get(full_href)
            inner_soup = BeautifulSoup(inner_r.content.decode(), 'html.parser')
            method, url = inner_soup.select_one('pre > code').text.split(' ')

            parsed_url = urlparse(url)
            paths = list(filter(None, parsed_url.path.split('/')))

            query, body, url_with_query = parse_page(inner_soup, url)
            headers = []
            if body:
                headers.append({
                    "key": "Content-Type",
                    "type": "text",
                    "value": "application/json"
                })

            operations.append({
                'name': name,
                "request": {
                    "method": method,
                    "header": headers,
                    "body": body,
                    "url": {
                        "raw": url,
                        "protocol": parsed_url.scheme,          # "https",
                        "host": parsed_url.netloc.split('.'),   # ["api", "powerbi", "com"],
                        "path": paths,                          # ["v1.0", "myorg", "groups"],
                        "query": query
                    },
                    "description": description_title + '<br>' + description_html
                },
                "response": [],
                '_link': full_href
            })

        lis[i]['item'] = operations

    postman_collection['item'] = lis
    with open(f"postman_collection {datetime.now().strftime('%Y-%m-%d %H;%M;%S')}.json", 'w') as f:
        json.dump(postman_collection, f)


if __name__ == '__main__':
    main()
