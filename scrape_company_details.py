import os
from time import sleep
from selenium import webdriver
# from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
from pyvirtualdisplay import Display
import boto3
from boto3.dynamodb.conditions import Key, Attr
import json

# from boto3.dynamodb.types import Decimal


def remove_uncide_characters(u_string):
    new_string = ""
    for letter in u_string:
        try:
            letter_str = str(letter)
            new_string += letter_str
        except UnicodeEncodeError:
            pass
    return new_string.replace('\xa0', ' ').replace(')AS OF', ') AS OF')


def get_page_source(driver, url, sleep_time=5):
    driver.get(url)
    sleep(sleep_time)
    return driver.page_source


def get_company_urls(urls_file_name):
    summary_urls = []
    if os.path.exists(urls_file_name):
        fh = open(urls_file_name)
        summary_urls = set([tuple(rec.strip("\n").split("|")) for rec in fh.readlines()])
        fh.close()
    else:
        print("File Not  Fund")
    return summary_urls


def get_price_details(soup):
    symbol_elem = soup.find("h2", {"class": "symbol"})
    last_price = symbol_elem.find("span", {"id": "lastPrice"}).text
    price_change_elem = symbol_elem.find("span", {"id": "priceChange"})
    price_change_direction = price_change_elem.find("img").attrs.get("alt", "")
    net_chage_today = price_change_elem.find("span", {"id": "netChgToday"}).text
    pct_change_today = price_change_elem.find("span", {"id": "pctChgToday"}).text
    pct_change_today = pct_change_today.replace("(", "").replace(")", "")
    as_of_text = symbol_elem.find("span", {"id": "timeAndDate"}).text
    statement = "stock price is ${0}, {1} by ${2}, changed, {3}, {4}"
    return statement.format(last_price, price_change_direction, net_chage_today, pct_change_today, as_of_text)


def get_company_profile(soup):
    comp_profile_elem = soup.find("div", {"id": "companyProfile"})
    company_profile = comp_profile_elem.find("div", {"id": "busDesc-more"}).find("p").text
    return company_profile


def get_sector_data(soup):
    company_profile_elem = soup.find("div", {"id": "companyProfile"})
    gics_sector = company_profile_elem.find_all("div", {"class": "sub-heading"})[0].find("a").text
    gics_industry = company_profile_elem.find_all("div", {"class": "sub-heading"})[1].find("a").text
    return gics_sector, gics_industry


def get_compare_data(soup):
    comp_data = []
    div_compare = soup.find("div", {"id": "compare"})
    # sector_name = div_compare.find("div", {"id": "comparison"}).find("a").text
    comp_table_elem = div_compare.find("table")
    row_elem = comp_table_elem.find_all("tr")
    # header = [elem.text for elem in row_elem[0].find_all("th")]
    # comp_data.append(header)
    statement1 = "{0} is {1} vs  average of {2}"
    statement2 = "{0} is {1}"
    for row in row_elem[1:]:
        label = str(remove_uncide_characters(row.find("th").text))
        stock_value = remove_uncide_characters(str(row.find_all("td")[0].text)).replace('--', '')
        industry_value = remove_uncide_characters(str(row.find_all("td")[1].text).replace('--', ''))
        if (stock_value):
            if (industry_value):
                data = statement1.format(label, stock_value, industry_value)
                comp_data.append(data)
            else:
                data = statement2.format(label, stock_value)
                comp_data.append(data)
    return comp_data


def get_stock_data(soup, symbol, name):
    stock_data = {}
    stock_data['stock_symbol'] = symbol
    stock_data['stock_name'] = name
    stock_data['price_comments'] = get_price_details(soup)
    stock_data['company_profile'] = get_company_profile(soup)
    stock_data['industry_comparision'] = get_compare_data(soup)
    return stock_data


def get_stock(stock_symbol, pe=None):
    response = table.query(KeyConditionExpression=Key('stock_symbol').eq(stock_symbol))
    # print(response)
    if response['Count'] > 0:
        return response['Items'][0]


if __name__ == '__main__':
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table("stock_details")

    summary_urls = get_company_urls('company_urls.txt')
    print("There are total {0} stocks".format(len(summary_urls)))
    #display = Display(visible=0, size=(1024, 768))
    # display.start()
    driver = webdriver.Chrome()
    # base_url = "https://www.fidelity.com/fund-screener/evaluator.shtml#!&mgdBy=F&ntf=N&pgNo={0}"
    stock_out = open("stock_details.json", "w")
    print(list(summary_urls)[0])
    for name, symbol, url in list(summary_urls)[0:3]:
        #item = ""
        # if symbol:
        #    print(symbol)
        #    item = get_stock(symbol)
        if url:
            try:
                print("started - {0}".format(name))
                page_source = get_page_source(driver, url)
                soup = BeautifulSoup(page_source, 'lxml')
                stock_data = get_stock_data(soup, symbol, name)
                # table.put_item(Item=stock_data)
                stock_out.write(json.dumps(stock_data))
                stock_out.write("\n")
            except Exception as e:
                print("Error occured  for {0}".format(name))
                print(name, symbol)
                print(e)
    driver.close()
    stock_out.close()
