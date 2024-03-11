import json
from bs4 import BeautifulSoup
from constants import *
from factory import *

class Config:
    def __init__(self, **conf):
        self.model = conf["model"]
        self.task = conf["task"]


def load_config(conf_path: str):
    """Load configuration"""
    with open(conf_path, "r") as f:
        conf = json.load(f)
    config = Config(**conf)
    return config


def init_factory(config: Config):
    """
    """
    if config.task == BOOKMARK_CLASSIFICATION_TASK:
        factory = BookmarkClassifierFactory(config)
    else:
        raise ValueError("Task is not supported")
    return factory



def read_in_file(filename): 
    f = open(filename, 'r') 
    soup = BeautifulSoup(f.read(), 'html.parser')
    f.close()
    return soup


def parse_html(soup):
    res = []
    for line in soup.find_all('a'):
        url = line.get('href')
        description = line.get_text()
        res.append({'html_str': line, 'url': url, 'description': description})
    return res