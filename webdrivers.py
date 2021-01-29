from bs4 import BeautifulSoup
import subprocess
import platform
import requests
import zipfile
import urllib
import os


def download(url, target):
    try:
        urllib.request.urlretrieve(url, target)
    except Exception as e:
        print(f'Check download url,path: {url}, {target}')


def unzip(zip_file, target_dir):
    try:
        with zipfile.ZipFile(zip_file) as zf:
            zf.extractall(path=target_dir)
    except Exception as e:
        print(f'Unzip {e}')


def remove(path):
    os.remove(path)


def check_chrome_version(chrome_path=None):
    if platform.system() == 'Windows':
        if chrome_path is not None:
            chrome = os.path.join(chrome_path)
        elif platform.architecture()[0] == '64bit':
            chrome = r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
        else:
            chrome = r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        if not os.path.exists(chrome):
            raise FileNotFoundError(f'chrome.exe is not exist at {chrome}. Download Chrome first.')

        version = subprocess.check_output(f'wmic datafile where name="{chrome}" get Version /value',
                                          shell=True).decode('utf-8').strip().split('=')[1]
    else:
        raise NotImplementedError('Other OS is not implemented')

    return version


def download_chrome_driver(target_dir='.', version=None):
    if version is None:
        version = check_chrome_version()
    target = os.path.join(target_dir, 'chromedriver.exe')
    if not os.path.exists(target):
        print(f'{target} is not exist. Download Chrome driver')
        _download_chrome_driver(version, target_dir)

    return target


def _download_chrome_driver(version, target):
    # check platform
    if platform.system() == 'Windows':
        basename = 'chromedriver_win32.zip'
    elif platform.system() == 'Linux':
        basename = 'chromedriver_linux64.zip'
    elif platform.system() == 'Mac':
        basename = 'chromedriver_mac64.zip'
    else:
        raise ValueError('Platform')

    # find proper driver version
    _version = version.split('.')
    downloadable_driver_list_url = 'https://chromedriver.chromium.org/downloads'
    _list = requests.get(downloadable_driver_list_url)
    if _list.status_code != 200:
        raise ConnectionError(f'Check driver url: {downloadable_driver_list_url}')
    _links = BeautifulSoup(_list.content, 'html.parser').select("a")
    versions = sorted(map(lambda x: x.attrs['href'].split('=')[1],
                          filter(lambda x: x.get_text().startswith(f'ChromeDriver {_version[0]}'), _links)),
                      reverse=True)
    if not len(versions):
        raise ValueError('No matched major version')

    # download
    download_server = 'https://chromedriver.storage.googleapis.com/'
    download_url = f'{download_server}{versions[0]}{basename}'
    download(download_url, 'chromedriver.zip')
    unzip('chromedriver.zip', target)
    remove('chromedriver.zip')


if __name__ == '__main__':
    from selenium import webdriver

    d = download_chrome_driver('webdriver')

    driver = webdriver.Chrome(d)
    d = download_chrome_driver('.')
    driver2 = webdriver.Chrome(d)
