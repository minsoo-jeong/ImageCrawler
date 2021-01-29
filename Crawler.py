from webdrivers import download_chrome_driver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium import webdriver

from multiprocessing import Pool
from urllib.parse import quote
from tqdm import tqdm

import requests
import shutil
import base64
import json

import time
import re
import os


class ImageCrawler:
    def __init__(self, site=('naver', 'google', 'pinterest'), show=True, thumbnail=True, core=-1):
        assert len(site)
        driver_dir = 'webdriver'
        self.driver_path = download_chrome_driver(driver_dir)

        self.options = webdriver.ChromeOptions()
        if not show:
            self.options.add_argument('--headless')
        self.options.add_argument("--disable-xss-auditor")
        self.options.add_argument("--disable-web-security")
        self.options.add_argument("--allow-running-insecure-content")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-setuid-sandbox")
        self.options.add_argument("--disable-webgl")
        self.options.add_argument("--disable-popup-blocking")
        self.options.add_argument('--window-size=2560,1440')
        self.options.add_argument("--disable-gpu")

        self.site = [getattr(self, s) for s in site if hasattr(self, s)]

        self.thumbnail = thumbnail
        self.core = core

    def get_urls(self, keywords):

        pool = Pool(self.core) if self.core > 0 else Pool()
        result = {k: {s.__name__: pool.apply_async(s, args=(k,)) for s in self.site} for k in keywords}

        pool.close()
        pool.join()

        urls = dict()
        for k in keywords:
            k_urls = []
            for s in self.site:
                k_urls.extend(result[k][s.__name__].get())
            urls[k] = self.remove_duplicate_urls(k_urls)
            print(f'Remove duplicate {k}: {len(k_urls)} -> {len(urls[k])}')

        return urls

    def naver(self, keyword):
        def query(driver, keyword):
            driver.get(f'https://search.naver.com/search.naver?where=image&sm=tab_jum&query={quote(keyword)}')
            driver.implicitly_wait(3)

        def infinite_scroll_down(driver, wait=.5):
            body = driver.find_element_by_tag_name('body')
            while True:
                body.send_keys(Keys.END)
                if driver.find_elements(By.XPATH, '//div[contains(@class,"photo_loading")]')[0].get_attribute(
                        'style') == '':
                    time.sleep(wait)
                else:
                    break
            time.sleep(wait)

        def get_thumbnail_urls(driver, wait=.1, retry=3):
            empty_src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
            urls = []
            imgs = driver.find_elements(By.XPATH, '//img[@class="_image _listImage"]')
            for img in imgs:
                count = retry
                while count:
                    src = img.get_attribute('src')
                    if src == empty_src:
                        src = img.get_attribute('data-lazy-src')
                    if src is not None and src != empty_src:
                        urls += [src]
                        break
                    count -= 1
                    time.sleep(wait)

            return urls

        def get_image_urls(driver, wait=.1, retry=3):
            def check_loaded(img):
                return False if img.get_attribute('src').endswith('type=a340') else True

            body = driver.find_element_by_tag_name('body')
            body.send_keys(Keys.HOME)
            imgs = driver.find_elements(By.XPATH, '//img[@class="_image _listImage"]')
            urls = []
            for n, img in enumerate(imgs):
                if n == 0:
                    img.click()

                count = retry
                origin_img = driver.find_element(By.XPATH, '//div[@class="image _imageBox"]//img')
                while count and not check_loaded(origin_img):
                    time.sleep(wait)
                    count -= 1

                if check_loaded(origin_img):
                    urls.append(origin_img.get_attribute('src'))

                body.send_keys(Keys.RIGHT)

            return urls

        driver = webdriver.Chrome(self.driver_path, options=self.options)
        query(driver, keyword)
        infinite_scroll_down(driver)
        urls = get_thumbnail_urls(driver) if self.thumbnail else get_image_urls(driver)

        print(f'[Naver] Get {len(urls)} {keyword} images.')
        driver.close()

        return urls

    def google(self, keyword):
        # https://www.reddit.com/r/explainlikeimfive/comments/2ecozy/eli5_when_you_search_for_something_on_google_the/
        # https://webapps.stackexchange.com/questions/58550/what-does-tbm-mean-in-google-search
        def query(driver, keyword):
            driver.get(f"https://www.google.com/search?q={quote(keyword)}&tbm=isch")
            driver.implicitly_wait(3)

        def infinite_scroll_down(driver, wait=.5):
            body = driver.find_element_by_tag_name('body')
            # more result btn
            while driver.find_element(By.XPATH, '//input[@class="mye4qd"]').is_displayed() is False:
                body.send_keys(Keys.END)
                time.sleep(wait)
            driver.find_element(By.XPATH, '//input[@class="mye4qd"]').click()
            while driver.find_element(By.XPATH, '//div[@class="OuJzKb Bqq24e"]').text != '더 이상 표시할 콘텐츠가 없습니다.':
                body.send_keys(Keys.END)
                time.sleep(wait)
            body.send_keys(Keys.END)

        def get_thumbnail_urls(driver, wait=.1, retry=3):
            imgs = driver.find_elements(By.XPATH, '//img[@class="rg_i Q4LuWd"]')
            urls = []
            for img in imgs:
                count = retry
                while count:
                    src = img.get_attribute('src')
                    if src is None:
                        src = img.get_attribute('data-src')
                    if src is not None:
                        urls += [src]
                        break
                    count -= 1
                    time.sleep(wait)

            return urls

        def get_image_urls(driver, wait=.5, retry=5):
            def check_loaded():
                loading_bar = driver.find_element(By.XPATH,
                                                  '//div[@class="tvh9oe BIB1wf"]//div[@class="k7O2sd"]')
                status = loading_bar.get_attribute('style') == 'display: none;'
                return status

            body = driver.find_element_by_tag_name('body')
            body.send_keys(Keys.HOME)

            imgs = driver.find_elements_by_xpath('//img[@class="rg_i Q4LuWd"]')

            urls = []
            for n, img in enumerate(imgs):
                if n == 0:
                    img.click()

                count = retry
                while count and not check_loaded():
                    time.sleep(wait)
                    count -= 1

                if check_loaded():
                    xpath = '//div[@class="tvh9oe BIB1wf"]//img[@class="n3VNCb"]'
                    urls.append(driver.find_element_by_xpath(xpath).get_attribute('src'))
                body.send_keys(Keys.RIGHT)
            return urls

        driver = webdriver.Chrome(self.driver_path, options=self.options)
        query(driver, keyword)
        infinite_scroll_down(driver)
        urls = get_thumbnail_urls(driver) if self.thumbnail else get_image_urls(driver)
        driver.close()
        print(f'[Google] Get {len(urls)} {keyword} images.')
        return urls

    def pinterest(self, keyword):
        def query(driver, keyword):
            driver.get(
                f"https://www.pinterest.co.kr/search/pins/?q={quote(keyword)}")
            driver.implicitly_wait(3)

        def infinite_scroll_down(driver, wait=.5, retry=10):
            body = driver.find_element_by_tag_name('body')
            body.send_keys(Keys.HOME)

            h = driver.execute_script("return window.pageYOffset")
            count = retry
            while count:
                body.send_keys(Keys.END)
                n_h = driver.execute_script("return window.pageYOffset")
                if n_h == h:
                    count -= 1
                else:
                    count = retry
                h = n_h
                time.sleep(wait)

            body.send_keys(Keys.END)

        def get_image_urls_unauthorized(driver, thumbnail=False):
            body = driver.find_element_by_tag_name('body')
            body.send_keys(Keys.HOME)
            imgs = driver.find_elements(By.XPATH, '//img[@class="GrowthUnauthPinImage__Image"]')
            # imgs = driver.find_elements(By.XPATH, '//img[@class="hCL kVc L4E MIw"]')
            urls = []
            for img in imgs:
                if thumbnail:
                    urls += [img.get_attribute('src')]
                else:
                    urls += [img.get_attribute('src')] if not img.get_attribute('srcset') else [
                        re.findall(r'(https?://\S+)', img.get_attribute('srcset'))[-1]]

            return urls

        driver = webdriver.Chrome(self.driver_path, options=self.options)

        query(driver, keyword)

        infinite_scroll_down(driver)

        urls = get_image_urls_unauthorized(driver, self.thumbnail)

        driver.close()

        print(f'[Pinterest] Get {len(urls)} {keyword} images.')
        return urls

    def remove_duplicate_urls(self, urls):
        _urls = list(set(urls))
        return _urls

    def download(self, urls, target):

        def update(progress, x, n, src):
            progress.update()
            if not x:
                progress.write(f'{n}: {src} Fail to download')

        if not os.path.exists(target):
            os.makedirs(target)

        progress = tqdm(urls, unit='images',
                        bar_format='{desc} - {n_fmt}/{total_fmt} [{bar:15}] - {elapsed_s:.0f}s {rate_inv_fmt}',
                        ascii=" =",
                        mininterval=1,
                        ncols=150)
        progress.set_description_str(os.path.basename(target))
        pool = Pool()
        results = []

        for n, src in enumerate(urls):
            if src.startswith('http'):
                results += [pool.apply_async(self.download_from_url, args=(src, target, n),
                                             callback=lambda x: update(progress, x, n, src))]

            elif src.startswith('data'):
                results += [pool.apply_async(self.download_from_base64, args=(src, target, n),
                                             callback=lambda x: update(progress, x, n, src))]

        pool.close()
        pool.join()

        progress.close()

    def get_image_extension(self, type):
        content, ext = type.split('/')
        if content.lower() != 'image' or re.match('(gif|jpe?g|tiff?|png|webp|bmp)', ext) is None:
            raise NotImplementedError(f'Unsupported type: {type}')
        else:
            if ext == 'jpeg':
                ext = 'jpg'
            elif ext == 'tif':
                ext = 'tiff'
            return ext

    def download_from_url(self, url, target, name):
        result = False
        try:
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                ext = self.get_image_extension(response.headers.get('content-type'))
                dst = os.path.join(target, f'{name}.{ext}')
                with open(dst, 'wb') as f:
                    shutil.copyfileobj(response.raw, f)
                result = dst
        except Exception as e:
            pass
        return result

    def download_from_base64(self, src, target, name):
        result = False
        try:
            _, content_type, _, data = re.split(':|;|,', src)
            ext = self.get_image_extension(content_type)
            dst = os.path.join(target, f'{name}.{ext}')
            image = base64.b64decode(data)
            with open(dst, 'wb') as f:
                f.write(image)
            result = dst
        except Exception as e:
            pass
        return result

    def start(self, file, target):

        keywords = [k.strip() for k in open(file, 'r', encoding='utf-8').readlines()]

        urls = self.get_urls(keywords=keywords)
        for k, u in urls.items():
            crawler.download(u, os.path.join(target, k))

        json.dump(urls, open(os.path.join(target, 'urls.json'), 'w', encoding='utf-8'), ensure_ascii=False)


if __name__ == '__main__':
    crawler = ImageCrawler(site=['naver', 'google', 'pinterest'], thumbnail=True, show=True, core=3)

    crawler.start(file='keywords.txt', target=os.path.join('download', 'thumbnail'))
