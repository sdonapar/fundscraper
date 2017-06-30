import os
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
from pyvirtualdisplay import Display
import boto3
from boto3.dynamodb.types import Decimal
import json


def get_page_source(driver, url, sleep_time=5):
    driver.get(url)
    sleep(sleep_time)
    return driver.page_source


def get_summary_urls(page_source):
    urls = []
    soup = BeautifulSoup(page_source, 'lxml')
    links = soup.find_all("a")
    for anchor in links:
        anchor_href = anchor.attrs.get('href', '')
        if 'fundresearch' in anchor_href:
            urls.append(anchor_href)
    return urls


def get_fund_details(page_source):
    soup = BeautifulSoup(page_source, 'lxml')
    elements = soup.find_all("details-table-row")
    fund_details = []
    for elem in elements:
        if ('label' in elem.attrs.get('item', '')):
            try:
                my_dict = eval(elem.attrs.get('item', {}))
            except:
                my_dict = {}
            if my_dict:
                fund_details.append((str(my_dict.get('label', '')), str(my_dict.get('value', ''))))
    return fund_details


def get_fund_holdings_details(page_source):
    holdings = []
    soup = BeautifulSoup(page_source, 'lxml')
    holdings_elem = soup.find_all("div", {"class": "holding-data ng-scope"})
    for elem in holdings_elem:
        stock_symbol_elem = elem.find("a")
        stock_name_elem = elem.find("div", {"class": "holding-company ng-binding"})
        comp_symbol = ""
        comp_link = ""
        if (stock_symbol_elem):
            comp_symbol = str(stock_symbol_elem.text)
            comp_link = str(stock_symbol_elem.attrs.get("href", ""))
        comp_name = str(stock_name_elem.text)
        if comp_name:
            my_doc = {'name': comp_name, 'symbol': comp_symbol, 'link': comp_link}
            holdings.append(my_doc)
    return holdings


def get_fund_holdings(page_source):
    holdings = []
    soup = BeautifulSoup(page_source, 'lxml')
    holdings_elem = soup.find_all("div", {"class": "holding-company ng-binding"})
    for elem in holdings_elem:
        comp_name = str(elem.text)
        if comp_name:
            holdings.append(comp_name)
    return holdings


def get_fund_manager(page_source):
    fund_manager_name = ""
    soup = BeautifulSoup(page_source, 'lxml')
    fund_manager_elem = soup.find("h2", {"class": "fund-manager-ind--single-manager-name ng-binding"})
    if fund_manager_elem:
        fund_manager_name = str(fund_manager_elem.text)
    return fund_manager_name


def remove_uncide_characters(u_string):
    new_string = ""
    for letter in u_string:
        try:
            letter_str = str(letter)
            new_string += letter_str
        except UnicodeEncodeError:
            pass
    return new_string


def get_fund_name(page_source):
    soup = BeautifulSoup(page_source, 'lxml')
    title = soup.title.text
    title_new = remove_uncide_characters(title)
    title_parts = title_new.split()
    fund_ticker = str(title_parts[0])
    fund_long_name = str(title_parts[2]) + ' ' + str(' '.join(title_parts[3:-3]))
    fund_short_name = fund_long_name.replace('Fidelity', '').replace('Portfolio', '').replace('Fund', '')
    fund_short_name = fund_short_name.lower()
    return (fund_ticker, fund_short_name, fund_long_name)


def get_fund_objectives(page_source):
    fund_text = {}
    soup = BeautifulSoup(page_source, 'lxml')
    fund_card = soup.find("div", {"class": "fund-overview-data-card--container"})
    fund_card_span = fund_card.find_all("span")
    for span_elem in fund_card_span:
        if 'strategyData' in span_elem.attrs.get('ng-bind-html', ''):
            fund_text['fund_strategy'] = str(span_elem.text)
    p_elements = soup.find_all("p")
    for p_elem in p_elements:
        ng_bind_html = p_elem.attrs.get('ng-bind-html', '')
        if ng_bind_html == "desc.objectivetext":
            fund_text['fund_objective'] = str(p_elem.text)
        elif ng_bind_html == 'desc.riskText':
            fund_text['fund_risk'] = str(p_elem.text)
    return fund_text


def get_fund_urls(urls_file_name, base_url):
    summary_urls = []
    if os.path.exists(urls_file_name):
        fh = open(urls_file_name)
        summary_urls = [rec.strip("\n") for rec in fh.readlines()]
        fh.close()
    else:
        for page_number in range(1, 17):
            page_url = base_url.format(page_number)
            page_source = get_page_source(driver, page_url)
            urls = get_summary_urls(page_source)
            summary_urls.extend(urls)
        out_file = open(urls_file_name, 'w')
        for url in summary_urls:
            out_file.write(url)
            out_file.write("\n")
        out_file.close()
    return summary_urls


def get_fund_data(driver, url):
    fund_data = {}

    fund_id = url.split('/')[-1]
    page_source = get_page_source(driver, url)
    fund_ticker, fund_short_name, fund_long_name = get_fund_name(page_source)
    fund_details = get_fund_details(page_source)
    fund_manager = get_fund_manager(page_source)
    fund_holdings = get_fund_holdings(page_source)
    fund_holdings_details = get_fund_holdings_details(page_source)
    #fund_text = get_fund_objectives(page_source)
    fund_data['fund_id'] = fund_id
    fund_data['fund_short_name'] = fund_short_name
    fund_data['fund_long_name'] = fund_long_name
    fund_data['fund_ticker'] = fund_ticker
    fund_data['fund_manager'] = fund_manager
    fund_data['top10_holdings'] = fund_holdings
    fund_data['holdings'] = fund_holdings_details
    for key, value in fund_details:
        if key == "NAV":
            #value = Decimal(value.replace('$', '').replace(',', ''))
            value = value.replace('$', '').replace(',', '')
        if 'Portfolio Net Assets' in key:
            #value = Decimal(value.replace('$', '').replace(',', ''))
            value = value.replace('$', '').replace(',', '')
        fund_data[key] = value
    # for key in fund_text:
    #    fund_data[key] = fund_text[key]
    return fund_data


if __name__ == '__main__':
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table("fund_details")

    display = Display(visible=0, size=(1024, 768))
    display.start()
    driver = webdriver.Chrome()
    base_url = "https://www.fidelity.com/fund-screener/evaluator.shtml#!&mgdBy=F&ntf=N&pgNo={0}"

    summary_urls = get_fund_urls('fund_urls.txt', base_url)
    stock_urls = []

    fund_out = open("fund_details.json", "w")

    for url in summary_urls[0:]:
        fund_data = get_fund_data(driver, url)
        keys_to_be_deleted = []
        for key in fund_data:
            if not fund_data[key]:
                keys_to_be_deleted.append(key)

        for key in keys_to_be_deleted:
            del(fund_data[key])

        if (fund_data.get('fund_id', '') and fund_data.get('fund_short_name', '')):
            try:
                fund_holdings = fund_data.pop('holdings')
                # table.put_item(Item=fund_data)
                fund_out.write(json.dumps(fund_data))
                fund_out.write("\n")
                stock_urls.extend(fund_holdings)
                print("Completed extraction of fund_data:{0}, {1}".format(fund_data['fund_id'], fund_data['fund_short_name']))
            except Exception as e:
                print(e)
                print(fund_data.get('fund_id', 'unknown'))
        else:
            print("Not added: " + fund_data['fund_id'])

    fund_out.close()
    fh = open("company_urls.txt", "w")
    for doc in stock_urls:
        if (doc):
            fh.write("{0}|{1}|{2}\n".format(doc['name'], doc['symbol'], doc['link']))
    fh.close()
    driver.close()
