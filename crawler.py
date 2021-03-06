from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.common.exceptions import NoSuchElementException
from time import sleep
from os import system
import requests
import sys
import re

def browser():
	# Options for selenium
	options = Options()
	options.headless = True
	options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 11.4; rv:89.0) Gecko/20100101 Firefox/89.0")

	return webdriver.Firefox(options = options)#, capabilities=firefox_capabilities)


def get_source_code(browser, url):
	# get source code
	browser.get(url)
#	print(browser.execute_script("return navigator.userAgent"))
	html = browser.page_source
#	browser.close()

	return BeautifulSoup(html, 'html.parser')


def find_links(start_url, soup):
	links = []
	for link in soup.find_all(["a", "script", "button", "form"]):
		links.append(link.get('href'))
		links.append(link.get('src'))
		links.append(link.get('action'))
		links.append(link.get('load'))
		links.append(link.get('window.open'))
		links.append(link.get('window.location'))
		links.append(link.get('location.assign'))
		links.append(link.get('routerlink'))

	list_to_remove = [".js",".md",".com",".br",".edu",".us",".org","#",".pdf",".jpg",".png"]
	links_discard = set()

	links = set(links)
	links.discard(None)
	new_links = []

	links = list(links)
	for link in links:
		new_link = link.replace(start_url, "")
		if new_link != "":
			new_links.append(new_link)

	links = set(new_links)

	for link in links:
		for item in list_to_remove:
			if link.find(item) != -1:
				links_discard = links_discard.union([link])

	return links.difference(links_discard)



def find_login_page(links_in_start_url):
	return set([x for x in links_in_start_url if "login" in x])


def build_payload(soup_login_page, username_arg, password_arg):
	usernames_key = ["username", "usuário", "user", "uname", "email", "e-mail", "adminname"]
	passwords_key = ["password", "senha", "passwd", "pwd"]
	payload = {}
	
	for username in usernames_key:
		if soup_login_page.find_all('input', {'name':username}):
			payload[username] = username_arg
			break
	
	for password in passwords_key:
		if soup_login_page.find_all('input', {'name':password}):
			payload[password] = password_arg
			break

	return payload


def log_in(browser, start_url, login_page, payload):
	browser.get(start_url+login_page)
	#time.sleep(3)
	page_source_login = browser.page_source
	username = browser.find_element_by_name(list(payload.keys())[0])
	password = browser.find_element_by_name(list(payload.keys())[1])
	username.send_keys(list(payload.values())[0])
	password.send_keys(list(payload.values())[1])
	login_attempt = browser.find_element_by_xpath("//*[@type='submit']")
	login_attempt.click()
	page_text = (browser.find_element_by_tag_name('body').text).lower() # Get a visible text in the page
	redirected_page_source_login = browser.page_source

	#Check if the login was successful
	if page_source_login == redirected_page_source_login:
		return False
	key_words = ["invalid", "incorrect", "invalido", "incorreto"]
	for key_word in key_words:
		if key_word in page_text: 
			return False

	# Get cookies
	cookies_list = browser.get_cookies()
	cookies_dict = {}
	for cookie in cookies_list:
		cookies_dict[cookie['name']] = cookie['value']

	return [cookies_dict, browser.current_url]


def login_wordlist(browser, start_url, login_page, payload):
	for line in open("wordlist","r").readlines():
		line = line.strip()
		loginInfo = line.split(",")

		for n,input_dict in enumerate(payload):
			payload[input_dict] = loginInfo[n]

		login = log_in(browser, start_url, login_page, payload)
		
		if login is not False:
			return loginInfo

	return False


def check_login_wordlist(browser, start_url, login_page, payload):
	system('cls||clear')
	print("Trying to find a valid username and password combination...\n")
	logged_wordlist = login_wordlist(browser, start_url, login_page, payload)

	if logged_wordlist is not False:
		print("The username and password ",logged_wordlist," is valid in the page ",start_url+login_page,
			". The web system is vulnerable.\n")
		return logged_wordlist

	print("Not found a valid username and password combination!\n")

	return ["", ""]


def find_all_links(browser, login, start_url, links):
	if login is not False:
		cookies_dict = dict(login[0])
		for cookie in cookies_dict:
			browser.add_cookie({'name': cookie, 'value': cookies_dict[cookie]})
	
	links_to_crawl = links
	links_not_crawl = set()
	links_old = set()

	while True:
		for link in links_to_crawl:
			try:
				soup_page = get_source_code(browser, start_url+link)
				links = links.union(find_links(start_url, soup_page))
				links_to_crawl = links_to_crawl.union(links.difference(links_old))
				links_not_crawl = links_not_crawl.union([link])

				try:
					intputs_text = browser.find_elements_by_xpath("//input[@type='text']")
					for input_text in intputs_text:
						input_text.send_keys("default")
				except NoSuchElementException:
					pass

				try:
					intputs_text = browser.find_elements_by_xpath("//textarea[*]")
					for input_text in intputs_text:
						input_text.send_keys("default")
				except NoSuchElementException:
					pass
				
				try:
					browser.find_element_by_xpath("//*[@type='submit']").click()
				except NoSuchElementException:  #spelling error making this code not work as expected
					try:
						browser.find_element_by_xpath(".//*/form/input[2]").click()
					except NoSuchElementException:
						pass

				current_url = browser.current_url.replace(start_url, "")
				if current_url not in links:
					links_to_crawl = links_to_crawl.union([current_url])
					links = links.union([current_url])

			except:
				pass
		
		for link in links_to_crawl:
			if "?" in link and bool(re.search(r'\d', link)): #re.findall('(.+)\?', link)[0] in links:
				links_not_crawl = links_not_crawl.union([link])

		links_to_crawl = links_to_crawl.difference(links_not_crawl)
		links_not_crawl = set()

		if links_old == links:
			break

		links_old = links
		 
	return links		



def main():
	len_argv = len(sys.argv)
	if len_argv <= 1 or sys.argv[1]=="help":
		print("You need to pass an input url. You can also pass in a valid username and password.\nAn example is running 'python3 http://url username password'.")
		sys.exit()

	if len_argv == 3:
		print("You just filled in the username, fill in the password as well or just enter the url.\nYou can also pass in a valid username and password. An example is running 'python3 http://url username password'.")
		sys.exit()

	if (len_argv == 2 or len_argv == 4) and "http" not in sys.argv[1]:
		print("The url is invalid.")
		sys.exit()

	start_url = str(sys.argv[1])
	if start_url[len(start_url)-1] != "/":
		start_url = start_url+"/"
	browser_default = browser()
	page_source_start_url = get_source_code(browser_default, start_url)
	links_in_start_url = find_links(start_url, page_source_start_url)
	login_pages = find_login_page(links_in_start_url)
	links = login_pages

	username_arg = ""
	password_arg = ""

	if login_pages != set():
		for login_page in login_pages:
			if len_argv == 4:
				username_arg = str(sys.argv[2])
				password_arg = str(sys.argv[3])
				
			page_sorce_login = get_source_code(browser_default, start_url+login_page)
			payload = build_payload(page_sorce_login, username_arg, password_arg)
			
			login = log_in(browser_default, start_url, login_page, payload)

			if len_argv == 2 or login == False:
				logged_wordlist = check_login_wordlist(browser_default, start_url, login_page, payload)
				username_arg = logged_wordlist[0]
				password_arg = logged_wordlist[1]

				if username_arg != "":
					login = log_in(browser_default, start_url, login_page, payload)
			
			if login == False:
				print("\nThe username/password combination is invalid for "+start_url+login_page,"\n\n")

			else:
				links = links.union(set([login[1].replace(start_url, "")]))

			links = links.union(find_all_links(browser_default, login, start_url, links))

	else:
		links = links.union(find_all_links(browser_default, False, start_url, links))

	browser_default.close()

	print(links)


if __name__ == "__main__":
	main()
