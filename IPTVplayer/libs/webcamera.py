﻿# -*- coding: utf-8 -*-

###################################################
# LOCAL import
###################################################
from Plugins.Extensions.IPTVPlayer.dToolsSet.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.dToolsSet.iptvtools import printDBG, printExc, GetCookieDir, byteify, rm
from Plugins.Extensions.IPTVPlayer.itools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.dToolsSet.iptvplayerinit import SetIPTVPlayerLastHostError
from Plugins.Extensions.IPTVPlayer.icomponents.ihost import CBaseHostClass
###################################################

###################################################
# FOREIGN import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, ConfigText, getConfigListEntry
import re
import urllib
import random
import string
try:    import json
except Exception: import simplejson as json
############################################

###################################################
# E2 GUI COMMPONENTS 
###################################################
from Plugins.Extensions.IPTVPlayer.icomponents.asynccall import MainSessionWrapper
###################################################

###################################################
# Config options for HOST
###################################################

def GetConfigList():
    optionList = []
    return optionList
    
###################################################

class WebCameraApi(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self)
        self.MAIN_URL    = 'https://www.webcamera.pl/'
        self.DEFAULT_ICON_URL = 'http://static.webcamera.pl/webcamera/img/loader-min.png'
        self.HEADER = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:21.0) Gecko/20100101 Firefox/21.0', 'Referer':self.getMainUrl(), 'Accept': 'text/html'}
        self.AJAX_HEADER = dict(self.HEADER)
        self.AJAX_HEADER.update( {'X-Requested-With': 'XMLHttpRequest'} )
        
        self.COOKIE_FILE = GetCookieDir('webcamerapl')
        self.defaultParams = {'with_metadata':True, 'header':self.HEADER, 'save_cookie': True, 'load_cookie': True, 'cookiefile': self.COOKIE_FILE}
        self.cacheList = {}
        
    def getFullIconUrl(self, url, baseUrl=None):
        return CBaseHostClass.getFullIconUrl(self, url, baseUrl)
        
    def getFullUrl(self, url, baseUrl=None):
        if url == '#' or url == '/#': return ''
        return CBaseHostClass.getFullUrl(self, url, baseUrl)
    
    def getPage(self, baseUrl, addParams = {}, post_data = None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)
    
    def addDefaultIcons(self):
        for idx in range(len(self.currList)):
            if '' == self.currList[idx].get('icon', ''):
                self.currList[idx]['icon'] = self.getDefaulIcon()
    
    def getList(self, cItem):
        printDBG("WebCameraApi.getChannelsList")
        self.currList = []
        
        try:
            category = cItem.get('priv_category', '')
            if category == '':
                params = dict(cItem)
                params.update({'title':_('main'), 'priv_category':'list_items'})
                self.addDir(params)
                
                sts, data = self.getPage(self.getMainUrl())
                if not sts: return []
                data = self.cm.ph.getDataBeetwenMarkers(data, '<nav', '</nav>', False)[1]
                data = re.compile('(<li[^>]*?>|</li>|<ul[^>]*?>|</ul>)').split(data)
                if len(data) > 1:
                    try:
                        cTree = self.listToDir(data[1:-1], 0)[0]
                        params = dict(cItem)
                        params['c_tree'] = cTree['list'][0]
                        params['priv_category'] = 'list_categories'
                        self.listCategories(params, 'list_items')
                    except Exception:
                        printExc()
            elif category == 'list_categories':
                self.listCategories(cItem, 'list_items')
            elif category == 'list_items':
                page = cItem.get('page', 1)
                getPageParams = dict(self.defaultParams)
                if page > 1: self.defaultParams['header']['X-Requested-With'] = 'XMLHttpRequest'

                sts, data = self.getPage(cItem['url'], getPageParams)
                if not sts: return []

                if page == 1:
                    tmp = self.cm.ph.getSearchGroups(data, '''(<div[^>]+?inline\-camera\-listing[^>]+?>)''')[0]
                    printDBG(">> \"%s\"" % tmp)
                    tmp = re.compile('''data\-([^=^'^"^\s]+?)\s*=\s*['"]([^'^"]+?)['"]''').findall(tmp)
                    cItem = dict(cItem)
                    cItem['more_params'] = {}
                    for item in tmp:
                        cItem['more_params'][item[0]] = item[1]
                    cItem['more_url'] = self.cm.ph.getSearchGroups(data, '''['"]([^'^"]*?/ajax/[^'^"]+?)['"]''')[0]
                else:
                    try:
                        data = byteify(json.loads(data), '', True)['html']
                    except Exception:
                        printExc()
                        return []

                data = self.cm.ph.getAllItemsBeetwenNodes(data, ('<div', '>', 'inlinecam'), ('</div', '>'))
                vidCount = 0
                for item in data:
                    url = self.cm.ph.getSearchGroups(item, """href=['"]([^'^"]+?)['"]""")[0]
                    if '' != url:
                        title = self.cleanHtmlStr(item)
                        icon  = self.cm.ph.getSearchGroups(item, """data\-src=['"]([^'^"]+?)['"]""")[0]
                        if icon == '': icon  = self.cm.ph.getSearchGroups(item, """src=['"]([^'^"]+?\.jpg[^'^"]*?)['"]""")[0]
                        params = dict(cItem)
                        params.update({'title':title, 'url':self.getFullUrl(url), 'icon':self.getFullIconUrl(icon)})
                        self.addVideo(params)
                        vidCount += 1

                # check if next page is needed
                if vidCount > 0:
                    urlPrams = dict(cItem['more_params'])
                    urlPrams['page'] = page + 1
                    try: urlPrams['cameras'] = page * int(urlPrams['limit']) - 1
                    except Exception: printExc()
                    try: urlPrams['columns'] = page * (int(urlPrams['limit']) + 1)
                    except Exception: printExc()
                    
                    #urlPrams['cameras'] = '14'
                    #urlPrams['columns'] = '12'
                    
                    url = self.getFullUrl(cItem['more_url'])
                    url += '?' + urllib.urlencode(urlPrams)
                    getPageParams['header']['X-Requested-With'] = 'XMLHttpRequest'
                    sts, data = self.getPage(url, getPageParams)

                    if sts and data.startswith('{') and '"last":true' not in data: 
                        params = dict(cItem)
                        params.update({'title':_('Next page'), 'url':url, 'page':page+1})
                        self.addDir(params)
        except Exception:
            printExc()
        self.addDefaultIcons()
        return self.currList

    def getVideoLink(self, cItem):
        printDBG("WebCameraApi.getVideoLink")
        sts, data = self.getPage(cItem['url'])
        if not sts: return []
        videoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']+?embed[^"^']+?)['"]''', 1, True)[0]
        if videoUrl == '': videoUrl = self.cm.ph.getSearchGroups(data, '''<iframe[^>]+?src=['"]([^"^']*?/player/[^"^']+?)['"]''', 1, True)[0]
        url = self.getFullUrl(videoUrl)
        if 'youtube' in videoUrl and 'v=' not in videoUrl:
            sts, data = self.getPage(videoUrl)
            if not sts: return []
            videoUrl = self.cm.ph.getSearchGroups(data, '''<link[^>]+?rel=['"]canonical['"][^>]+?href=['"]([^'^"]+?)['"]''')[0]
        else:
            videoUrl = cItem['url']
        return self.up.getVideoLinkExt(videoUrl)
        
    def listCategories(self, cItem, nextCategory):
        printDBG("WebCameraApi.listCategories")
        try:
            cTree = cItem['c_tree']
            for item in cTree['list']:
                title = self.cleanHtmlStr(item['dat'])
                url   = self.getFullUrl(self.cm.ph.getSearchGroups(item['dat'], '''href=['"]([^'^"]+?)['"]''')[0])
                icon  = self.getFullIconUrl(self.cm.ph.getSearchGroups(item['dat'], '''src=['"]([^'^"]+?\.jpe?g(:?\?[^'^"]+?)?)['"]''')[0])
                if '/mapa' in url:
                    break
                elif 'list' not in item:
                    if self.cm.isValidUrl(url) and title != '':
                        if url.endswith('/aktualnosci'): continue # not handled at now
                        params = dict(cItem)
                        params.pop('c_tree', None)
                        params.update({'priv_category':nextCategory, 'title':title, 'url':url, 'icon':icon})
                        if url.endswith('/tv'): self.addVideo(params)
                        else: self.addDir(params)
                elif len(item['list']) == 1 and title != '':
                    obj = item['list'][0]
                    if url != '' and 'list' in obj:
                        obj['list'].insert(0, {'dat':'<a href="%s">%s</a>' % (url, _('--All--'))})
                    params = dict(cItem)
                    params.update({'c_tree':obj, 'title':title, 'url':url, 'icon':icon})
                    self.addDir(params)
        except Exception:
            printExc()