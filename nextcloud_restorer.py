import requests
import xml.etree.ElementTree as ET
import sys
import logging
import contextlib
from requests_toolbelt import sessions
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from argparse import ArgumentParser

logger = logging.getLogger(__file__)


class NextcloudRestorer:
    def __init__(self, url, user, password, threads):
        self.__client = sessions.BaseUrlSession(base_url=url)
        self.__client.auth = requests.auth.HTTPBasicAuth(user, password)
        adapter = requests.adapters.HTTPAdapter(pool_maxsize=threads)
        self.__client.mount("http://", adapter)
        self.__client.mount("https://", adapter)
        self.__user = user
        self.__threads = threads

    def restore_item(self, item):
        move_resp = self.__client.request(
            "MOVE", item, headers={"Destination": item.replace("trash/", "restore/")}
        )
        move_resp.raise_for_status()

    def get_deleted_items(self):
        trash_bin_resp = self.__client.request(
            "PROPFIND", f"/remote.php/dav/trashbin/{self.user}/trash"
        )
        trash_bin_resp.raise_for_status()
        trash_bin_xml = ET.fromstring(trash_bin_resp.text)
        return [a.text for a in trash_bin_xml.findall(".//{DAV:}href")[1:]]

    def restore_all(self):
        deleted_items = self.get_deleted_items()
        with ThreadPoolExecutor(max_workers=self.__threads) as pool:
            jobs = []
            for deleted_item in deleted_items:

                def job(item):
                    while True:
                        with contextlib.suppress(Exception):
                            self.restore_item(item)
                            return

                jobs.append(pool.submit(job, deleted_item))
            for _ in tqdm(as_completed(jobs), total=len(jobs)):
                pass


def main():
    parser = ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("user")
    parser.add_argument("password")
    parser.add_argument("--threads", default=20, type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    restorer = NextcloudRestorer(args.url, args.user, args.password, args.threads)
    restorer.restore_all()


if __name__ == "__main__":
    main()
