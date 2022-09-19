import re
import time
import random
import requests
import pandas as pd
from bs4 import BeautifulSoup
from pymongo import MongoClient
from requests.exceptions import Timeout, RequestException

MONGO_HOST = 'localhost'
MONGO_PORT = 27017
DB_NAME = 'links'


class LinkParser:
    def __init__(self, start_url, sleep, key_word, user_agent, proxies=None,
                 retry_number=1, timeout=None):
        self.start_url = start_url
        self.sleep = sleep
        self.retry_number = retry_number
        self.key_word = key_word
        self.headers = {'User-Agent': f'{user_agent}'}
        self.proxies = proxies
        self.timeout = timeout
        self.increase_timeout = False

    def _get(self, url, headers, proxies, timeout):
        for i in range(self.retry_number):
            try:
                response = requests.get(url, headers=headers, proxies=proxies,
                                        timeout=timeout)
                if response.status_code == 200:
                    print(f"{url} - success!")
                    return response
            # not sure if we want to increase timeouts on unvalid links
            # except Timeout:
            #     if self.increase_timeout:
            #         print(f'{url} - got timeout...increasing')
            #         timeout = timeout + 15
            #     continue
            except RequestException:
                print(f"{url} - request failed!")
            time.sleep(self.sleep + random.random())
        return None

    def run(self, url):
        return self._get(url, headers=self.headers, proxies=self.proxies,
                         timeout=self.timeout)

    @staticmethod
    def remove_duplicates(lst: list):
        return list(set(lst))

    @staticmethod
    def make_url(item: tuple):
        item = list(item)
        item.insert(1, '://')
        return ''.join(item)

    @staticmethod
    def save_to_mongo(parse_object, db_name, db_collection, db_host=None,
                      db_port=None):
        with MongoClient(host=db_host, port=db_port) as client:
            db = client[db_name]
            for link in parse_object:
                db.get_collection(db_collection).update_one({
                    'link': link['link']}, {'$set': link},
                    upsert=True)

    def parse(self):
        page_response = self.run(self.start_url)
        parser = page_response.text
        soup = BeautifulSoup(parser, 'html.parser')
        # remove all script and style elements
        for script in soup(["script", "style"]):
            script.extract()

        # get page visible text
        page_visible_text = soup.get_text()

        # making page text to lower case to find case-sensitive words
        if self.key_word in page_visible_text.lower():
            print('string found in a file')
        else:
            print('string does not exist in a file')

        a_links = []
        for link in soup.find_all('a'):
            if link.get('href'):
                a_links.append(link['href'])

        # Removing navigation anchors from links
        a_links = [link for link in a_links if "#" not in link]

        a_links = [self.start_url + link for link in a_links if
                   'http://' and 'ftp://' and 'https://' not in link]

        r_links = re.findall(
            r'(http|ftp|https):\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])',
            parser)

        r_links = [self.make_url(i) for i in r_links]
        links = self.remove_duplicates(a_links + r_links)

        result = []

        for link in links:
            link_response = self.run(link)
            if link_response:
                status_code = link_response.status_code
                encodings = link_response.encoding
                elapsed = link_response.elapsed.total_seconds()
                result.append({'link': link_response,
                               'status_code': status_code,
                               'encodings': encodings,
                               'elapsed': elapsed})
        return result


if __name__ == "__main__":
    url_input = input('Type a valid start_url: ')

    agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " \
            "(KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"

    search_word = input('Type of keyword to search: ')

    site_parser = LinkParser(start_url=url_input, sleep=1, key_word=search_word,
                             user_agent=agent, timeout=5)

    result_list = site_parser.parse()
    df = pd.DataFrame(result_list)
    print(df)
    df.to_excel(r'links.xlsx', sheet_name='rental', index=False)
    data = df.to_dict(orient='records')

    # if we need to save data in database

    # with MongoClient(host=MONGO_HOST, port=MONGO_PORT) as client:
    #     db = client[DB_NAME]
    #     collection = db['links']
    #     for item in result_list:
    #         collection.update_one(
    #             {'link': item['link']}, {"$set": item}, upsert=True)
