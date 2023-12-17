import scrapy, requests
from urllib.parse import parse_qs
from http.cookies import SimpleCookie

import os, json, re
from os.path import join, isdir, isfile
import threading, configparser

MAX_CHARACTER_RETRIVAL_COUNT = 2000
CURRENT_CHARACTER_COUNT = 0


SAVE_DIR_ROOT = './dataset/'
HOSTNAME = 'https://.../'
LOGIN_ID = "..."
LOGIN_PASSWORD = "..."



# add additional header to simulate actual user behavior to prevent server from suspecting the crawler
custom_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',}


class CollectCharacterSpider(scrapy.Spider):
    
    name = 'collect_spider'
    custom_settings = { 
            'DOWNLOAD_DELAY': 5
    }
    
    # ====================
    # need to login first
    
    
    def start_requests(self):
    
        formdata = {
            'id': LOGIN_ID,
            'pw': LOGIN_PASSWORD,
            'act': 'login',
            'B1': '登入'
        }
        
        # send post request to mimic login action
        yield scrapy.FormRequest(url = HOSTNAME + 'signin.php', formdata = formdata, headers = custom_headers, callback = self.after_login)
        

    def after_login(self, response):
        status_code = response.status

        if status_code == 200:
            self.logger.info('Login successful!')
            
            # set cookies
            raw_cookies = response.headers.getlist('Set-Cookie')
            cookies_str = b'; '.join(raw_cookies).decode('utf-8')
            cookie = SimpleCookie()
            cookie.load(cookies_str)
            cookies_dict = {key: morsel.value for key, morsel in cookie.items()}
            self.logger.debug(f"cookies_dict:{cookies_dict}")
            
            # redirect to the character page
            yield scrapy.Request(url=HOSTNAME+'select_materials.php?show=char', cookies=cookies_dict, callback=self.parse_character_list)
            
        else:
            self.logger.error('Login failed. Check your credentials.')
    
    # ====================
    
    
    def parse_character_list(self, response):

        material_container = response.xpath('/html/body/div[3]/div[1]/div[1]')
        
        # check if it is an empty page
        if len(material_container.xpath('div')) < 4: # there should be above 4 elements
            self.logger.info('Reach the end of the character searching... abort.')
            return
            
        selected_divs = material_container.xpath('.//div[@class="material-box"]')

        for div in selected_divs:

            certain_character_link = HOSTNAME + div.xpath('./p[@class="content-desc"]/a[1]/@href').get()
            certain_character_id = parse_qs(certain_character_link.split('?')[1]).get('id')[0]
            self.logger.debug(f"certain_character_link : {certain_character_link}")
            self.logger.debug(f"certain_character_id : {certain_character_id}")
            
            character_info_dict = {}

            # --------------------------------
            # check if the character had already been properly processed before
            folder_path = join(SAVE_DIR_ROOT, certain_character_id)
            infofile_path = join(folder_path, "info.json")

            shouldCreateFolderTag = True
            shouldSaveInfoTag = True
            shouldYieldTag = True

            if isdir(folder_path):
                shouldCreateFolderTag = False
            if isfile(infofile_path):
                with open(infofile_path, "r", encoding='utf-8') as f:
                    character_info_dict = json.load(f)
                    """
                    # 'count' is not reliable
                    if 'count' in list(character_info_dict.keys()):
                        shouldSaveInfoTag = False
                        if len(os.listdir(folder_path))-1 == character_info_dict['count']:
                            # already handled properly before
                            continue
                    """
                    if 'isFinished' in list(character_info_dict.keys()):
                        shouldSaveInfoTag = False
                        if character_info_dict['isFinished']:
                            # already handled properly before
                            continue
            # --------------------------------
            
            global CURRENT_CHARACTER_COUNT
            if CURRENT_CHARACTER_COUNT >= MAX_CHARACTER_RETRIVAL_COUNT:
                # reach process limit, stop proceeding the task
                return
            CURRENT_CHARACTER_COUNT += 1
            

            if shouldCreateFolderTag:
                # create folder with character_id as name
                os.mkdir(folder_path)
            
            if shouldSaveInfoTag:
                # save character info in dict
                character_info_dict['id'] = certain_character_id
                character_info_dict['title'] = div.xpath('./p[@class="content-desc"]/b/text()').get()
                character_info_dict['author'] = div.xpath('./p[@class="content-desc"]/a[2]/text()').get()
                character_info_dict['count'] = int(div.xpath('./p[@class="content-desc"]/font/text()').get().split(' ')[1])
                character_info_dict['description'] = None
                character_info_dict['tags'] = []
                character_info_dict['poses'] = []
                character_info_dict['isFinished'] = False
                self.logger.debug(f"character_info_dict : {character_info_dict}")
                
                with open(infofile_path, 'w', encoding='utf-8') as f:
                    json.dump(character_info_dict, f, indent=2, ensure_ascii=False)
            
            if shouldYieldTag:
                self.logger.debug(f"================yield: {certain_character_id}")
                # need lock to protect correctness of info file
                file_lock = threading.Lock()

                # reset 'tags' and 'poses' in info.json
                with open(infofile_path, 'r+', encoding='utf-8') as f:
                    character_info_dict = json.load(f)
                    character_info_dict['tags'] = []
                    character_info_dict['poses'] = []
                    # overwrite original content
                    f.seek(0)
                    json.dump(character_info_dict, f, indent=2, ensure_ascii=False)
                    f.truncate()

                # further access all poses of the character with provided link
                yield scrapy.Request(url=certain_character_link, meta={'id': certain_character_id, 'lock': file_lock}, callback=self.parse_pose_list)
            
        
        # go to next page
        navigation_div = material_container.xpath('.//div[@class="btn-container"]')[0] # should only be 1 element
        next_list_link = HOSTNAME + navigation_div.xpath('.//a[2]/@href').get()
        self.logger.debug(f'next_list_link : {next_list_link}')
        yield scrapy.Request(url=next_list_link, callback=self.parse_character_list)
        

    def parse_pose_list(self, response):

        material_container = response.xpath('/html/body/div[3]/div[1]/div[1]')
        folder_path = join(SAVE_DIR_ROOT, response.meta.get('id'))
        
        # check if it is an empty page
        if len(material_container.xpath('div')) < 4: # there should be above 4 elements
            # ======================
            # set 'isFinished' parameter
            with response.meta.get('lock'):
                info_path = join(folder_path, "info.json")

                # use r+ mode to open file so that original content will be preserved
                with open(info_path, 'r+', encoding='utf-8') as f:
                    info_dict = json.load(f)
                    info_dict['isFinished'] = True
                    
                    # write back to the file
                    f.seek(0)
                    json.dump(info_dict, f, indent=2, ensure_ascii=False)
                    f.truncate() # make sure no leftover from old json
            # =======================
            
            self.logger.info('Reach the end of the character searching... abort.')
            return
        

        #-- 1. get addtional info to complete 'info.json' under character folder
        #-- following keys needs to be updated: description, tags, poses
        
        # (a) get description and parse into tags in the upper area
        #whole_paragraph = material_container.xpath('./p[@class="content-desc"]/text()').get()
        #description = whole_paragraph.split('<br>')[2]
        description = material_container.xpath('./p[@class="content-desc"]/br[2]/following-sibling::text()').get()
        new_tags = []
        if description != "" and description != None:
            new_tags = re.findall(r'\[([^\]]+)\]', description)
        self.logger.debug(f'new_tags : {new_tags}')

        # (b) get each pose of the character
        selected_divs = material_container.xpath('.//div[@class="material-box"]')

        new_poses = []
        for div in selected_divs:
            img_endpoint = div.xpath('.//center/img/@src').get()
            img_url = HOSTNAME + img_endpoint
            pose = div.xpath('.//center/font/text()').get()
            new_poses.append(pose)

            #-- 2. save character images under character folder
            #-- use pose as name, and 'png' as extension format
            extension = img_endpoint.split('.')[1]
            image_path = join(folder_path, pose+"."+extension)
            self.logger.debug(f"img_url : {img_url}")
            self.logger.debug(f"image_path : {image_path}")
            
            
            resp = requests.get(img_url, headers=custom_headers)
            # you will get 403 error code if you don't specify 'User-Agent' header
            # (Not Acceptable! An appropriate representation of the requested resource could not be found on this server. This error was generated by Mod_Security)
            
            if resp.status_code == 200:
                with open(image_path, 'wb') as f:
                    f.write(resp.content)

        # (c) update info_dict and maintain thread-safe with lock
        with response.meta.get('lock'):
            info_path = join(folder_path, "info.json")

            # use r+ mode to open file so that original content will be preserved
            with open(info_path, 'r+', encoding='utf-8') as f:
                info_dict = json.load(f)

                # -----
                # check if description already setted
                if info_dict['description'] == None:
                    info_dict['description'] = description
                    info_dict['tags'] = info_dict['tags'] + new_tags

                # add new elements to existing list
                info_dict['poses'] = info_dict['poses'] + new_poses
                # -----

                # write back to the file
                f.seek(0)
                json.dump(info_dict, f, indent=2, ensure_ascii=False)
                f.truncate() # make sure no leftover from old json
        
        
        #--4 go to next page
        navigation_div = material_container.xpath('.//div[@class="btn-container"]')[0] # should only be 1 element
        next_list_link = HOSTNAME + navigation_div.xpath('./a[3]/@href').get()
        self.logger.debug(f'next_list_link : {next_list_link}')
        yield scrapy.Request(url=next_list_link, meta={'id': response.meta.get('id'), 'lock': response.meta.get('lock')}, callback=self.parse_pose_list)
        

