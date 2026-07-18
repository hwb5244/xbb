import streamlit as st
import pandas as pd
import numpy as np
from collections import defaultdict, Counter
import os
from datetime import datetime
import json
import urllib.request
import urllib.error

# ==================== 【模块0】GitHub Gist API 云端持久化配置 ====================
GIST_CONFIG_KEY = 'gist_config'

def get_gist_config():
    """获取 Gist 配置"""
    if GIST_CONFIG_KEY not in st.session_state:
        st.session_state[GIST_CONFIG_KEY] = {
            'token': '',
            'lottery_gist_id': '',
            'predictions_gist_id': '',
            'hitrates_gist_id': ''
        }
    return st.session_state[GIST_CONFIG_KEY]

def save_gist_config(config):
    """保存 Gist 配置"""
    st.session_state[GIST_CONFIG_KEY] = config

def github_api_request(url, data=None, token=None, method=None):
    """通用的 GitHub API 请求"""
    headers = {
        'Accept': 'application/vnd.github.v3+json'
    }
    if token:
        headers['Authorization'] = f'token {token}'
    if data:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(data).encode('utf-8')
        method = method or 'PATCH'
    else:
        method = method or 'GET'
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8')), response.status
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        return {'error': error_body}, e.code
    except urllib.error.URLError as e:
        return {'error': str(e)}, -1

def get_or_create_gist(token, filename, content, description="快乐8预测系统数据"):
    """获取或创建 Gist（如果已存在则更新）"""
    if not token:
        return None, 'No token provided'
    
    url = f'https://api.github.com/gists'
    
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'Authorization': f'token {token}',
        'Content-Type': 'application/json'
    }
    
    data = json.dumps({
        'description': description,
        'public': False,
        'files': {
            filename: {
                'content': content
            }
        }
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['id'], None
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return None, 'Invalid GitHub Token'
        elif e.code == 404:
            return None, 'Not found'
        else:
            return None, f'HTTP Error: {e.code}'
    except urllib.error.URLError as e:
        return None, f'Network Error: {str(e)}'

def update_gist_content(token, gist_id, filename, content):
    """更新 Gist 内容"""
    if not token or not gist_id:
        return False, 'Missing token or gist_id'
    
    url = f'https://api.github.com/gists/{gist_id}'
    
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'Authorization': f'token {token}',
        'Content-Type': 'application/json'
    }
    
    data = json.dumps({
        'files': {
            filename: {
                'content': content
            }
        }
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=data, headers=headers, method='PATCH')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return True, None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, 'Gist not found'
        else:
            return False, f'HTTP Error: {e.code}'
    except urllib.error.URLError as e:
        return False, f'Network Error: {str(e)}'

def read_gist_content(token, gist_id, filename):
    """读取 Gist 内容"""
    if not token or not gist_id:
        return None, 'Missing token or gist_id'
    
    url = f'https://api.github.com/gists/{gist_id}'
    
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'Authorization': f'token {token}'
    }
    
    req = urllib.request.Request(url, headers=headers, method='GET')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            if filename in result['files']:
                return result['files'][filename]['content'], None
            else:
                return None, 'File not found in gist'
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, 'Gist not found'
        else:
            return None, f'HTTP Error: {e.code}'
    except urllib.error.URLError as e:
        return None, f'Network Error: {str(e)}'

def cloud_save_lottery_data(df, config):
    """云端保存基础号码库"""
    if not config['token']:
        return False, 'No token configured'
    
    csv_content = df.to_csv()
    
    if config['lottery_gist_id']:
        success, error = update_gist_content(
            config['token'],
            config['lottery_gist_id'],
            'lottery_data.csv',
            csv_content
        )
        if success:
            return True, None
        if 'not found' in str(error).lower():
            config['lottery_gist_id'] = ''
        else:
            return False, error
    
    gist_id, error = get_or_create_gist(
        config['token'],
        'lottery_data.csv',
        csv_content,
        '快乐8预测系统-基础号码库'
    )
    
    if gist_id:
        config['lottery_gist_id'] = gist_id
        return True, None
    else:
        return False, error

def cloud_load_lottery_data(config):
    """云端加载基础号码库"""
    if not config['token'] or not config['lottery_gist_id']:
        return None
    
    content, error = read_gist_content(
        config['token'],
        config['lottery_gist_id'],
        'lottery_data.csv'
    )
    
    if content:
        from io import StringIO
        df = pd.read_csv(StringIO(content), index_col='期号', dtype={'期号': str})
        return df
    return None

def cloud_save_predictions(predictions_data, config):
    """云端保存所有预测方案"""
    if not config['token']:
        return False, 'No token configured'
    
    content = json.dumps(predictions_data, ensure_ascii=False, indent=2)
    
    if config['predictions_gist_id']:
        success, error = update_gist_content(
            config['token'],
            config['predictions_gist_id'],
            'predictions.json',
            content
        )
        if success:
            return True, None
        if 'not found' in str(error).lower():
            config['predictions_gist_id'] = ''
        else:
            return False, error
    
    gist_id, error = get_or_create_gist(
        config['token'],
        'predictions.json',
        content,
        '快乐8预测系统-预测方案'
    )
    
    if gist_id:
        config['predictions_gist_id'] = gist_id
        return True, None
    else:
        return False, error

def cloud_load_predictions(config):
    """云端加载所有预测方案"""
    if not config['token'] or not config['predictions_gist_id']:
        return None
    
    content, error = read_gist_content(
        config['token'],
        config['predictions_gist_id'],
        'predictions.json'
    )
    
    if content:
        return json.loads(content)
    return None

def cloud_save_hit_rates(hit_rates_data, config):
    """云端保存所有命中率记录"""
    if not config['token']:
        return False, 'No token configured'
    
    content = json.dumps(hit_rates_data, ensure_ascii=False, indent=2)
    
    if config['hitrates_gist_id']:
        success, error = update_gist_content(
            config['token'],
            config['hitrates_gist_id'],
            'hit_rates.json',
            content
        )
        if success:
            return True, None
        if 'not found' in str(error).lower():
            config['hitrates_gist_id'] = ''
        else:
            return False, error
    
    gist_id, error = get_or_create_gist(
        config['token'],
        'hit_rates.json',
        content,
        '快乐8预测系统-命中率记录'
    )
    
    if gist_id:
        config['hitrates_gist_id'] = gist_id
        return True, None
    else:
        return False, error

def cloud_load_hit_rates(config):
    """云端加载所有命中率记录"""
    if not config['token'] or not config['hitrates_gist_id']:
        return None
    
    content, error = read_gist_content(
        config['token'],
        config['hitrates_gist_id'],
        'hit_rates.json'
    )
    
    if content:
        return json.loads(content)
    return None

# ==================== 【模块1】全局配置与数据持久化 ====================
st.set_page_config(
    page_title='快乐8多周期三流派预测系统',
    page_icon='🎱',
    layout='wide',
    initial_sidebar_state='expanded'
)

# 预加载的官方开奖数据（2025250-2025301，共51期）
INITIAL_DATA = [
    ["2025301",8,9,11,13,14,18,21,30,33,34,40,44,46,51,58,62,65,67,77,78],
    ["2025300",4,11,20,26,29,35,37,39,47,54,55,59,63,64,65,67,70,71,72,74],
    ["2025299",9,10,11,19,23,25,39,41,45,51,53,54,59,60,63,65,68,69,70,75],
    ["2025298",3,5,8,13,15,19,20,25,26,27,28,30,33,34,37,45,47,67,69,77],
    ["2025297",4,8,9,11,14,19,36,40,42,48,49,52,56,59,66,68,69,73,76,79],
    ["2025296",7,9,11,14,23,26,31,32,36,37,42,43,48,52,53,54,55,58,64,68],
    ["2025295",2,7,12,13,21,22,23,24,26,34,38,43,53,57,67,69,71,72,77,80],
    ["2025294",1,2,8,15,21,22,24,26,27,30,38,41,43,45,46,50,61,62,70,78],
    ["2025293",5,7,17,19,23,34,35,37,38,41,46,53,56,63,65,66,67,69,71,79],
    ["2025292",1,2,3,10,11,15,16,25,38,40,43,47,50,52,57,62,64,71,78,80],
    ["2025291",4,7,11,17,20,22,27,29,32,34,37,48,55,64,68,69,71,73,74,78],
    ["2025290",8,9,10,19,20,25,26,30,32,35,40,41,45,47,49,51,54,65,68,75],
    ["2025289",3,6,7,10,11,13,14,15,31,35,40,41,43,45,55,57,66,72,73,75],
    ["2025288",4,11,15,16,22,23,37,46,47,49,51,53,54,55,60,62,70,72,73,74],
    ["2025287",1,6,17,18,21,22,23,24,31,32,40,43,48,49,52,57,58,60,68,79],
    ["2025286",6,12,14,16,22,24,25,34,38,39,41,42,43,54,57,58,61,62,68,74],
    ["2025285",5,6,7,9,11,19,24,27,28,29,38,39,41,45,46,63,67,68,73,80],
    ["2025284",10,11,14,19,20,26,29,30,35,37,40,41,45,46,59,68,70,77,78,80],
    ["2025283",2,4,13,19,20,23,29,31,37,40,47,52,53,54,55,63,64,65,68,69],
    ["2025282",5,9,12,15,16,20,22,24,26,30,35,38,39,47,49,56,62,66,72,74],
    ["2025281",8,15,23,24,28,34,35,36,38,43,45,49,51,53,64,67,69,71,74,75],
    ["2025280",6,10,14,15,16,25,32,36,46,49,50,59,64,68,70,72,73,77,78,79],
    ["2025279",1,5,6,14,25,32,35,40,45,47,53,62,63,67,68,70,71,72,75,78],
    ["2025278",4,5,7,8,10,15,17,18,22,26,30,33,39,42,48,50,63,68,72,77],
    ["2025277",9,11,13,14,20,22,39,43,48,52,54,55,57,64,68,69,72,73,75,80],
    ["2025276",3,17,21,22,24,30,33,34,41,44,45,47,48,59,61,68,69,76,78,79],
    ["2025275",7,9,13,14,28,32,33,34,35,37,48,50,51,56,57,59,65,69,72,76],
    ["2025274",2,3,10,18,26,31,33,34,46,49,50,51,54,55,60,62,74,75,76,80],
    ["2025273",8,9,11,13,14,18,20,24,28,30,31,32,38,39,40,46,62,64,69,70],
    ["2025272",3,6,9,10,11,13,14,16,20,22,25,43,47,50,60,61,62,68,73,79],
    ["2025271",1,3,7,15,17,20,27,37,41,42,47,48,53,54,60,62,63,68,77,78],
    ["2025270",2,8,10,20,21,27,28,30,33,36,43,48,49,52,60,61,64,71,75,79],
    ["2025269",1,8,10,15,19,20,24,30,33,43,49,50,56,57,60,67,70,73,78,80],
    ["2025268",5,12,16,18,19,26,31,33,38,39,41,42,49,54,59,64,65,70,73,77],
    ["2025267",8,13,20,21,25,34,37,39,45,47,50,57,58,60,65,71,72,75,78,79],
    ["2025266",1,5,9,13,16,17,25,28,29,33,34,38,45,47,48,55,62,71,73,78],
    ["2025265",2,9,11,16,18,27,28,35,36,38,49,52,54,60,62,64,66,72,77,78],
    ["2025264",6,10,15,16,20,24,25,28,34,35,37,38,42,44,45,49,54,66,69,80],
    ["2025263",4,5,11,13,14,20,23,24,27,32,33,42,45,55,58,62,64,70,79,80],
    ["2025262",8,10,14,19,27,31,33,40,42,44,46,47,49,54,58,60,67,70,75,77],
    ["2025261",3,10,15,17,19,22,23,25,31,35,36,42,60,61,62,65,70,73,76,77],
    ["2025260",3,8,10,11,13,16,21,24,27,38,41,48,54,58,59,61,62,66,69,71],
    ["2025259",4,7,9,19,20,30,33,35,44,45,48,49,50,51,52,70,71,72,74,78],
    ["2025258",1,5,10,12,16,23,25,28,29,36,40,46,51,55,58,64,66,71,76,80],
    ["2025257",1,8,13,15,22,34,36,38,42,43,49,50,51,65,66,67,70,71,79,80],
    ["2025256",8,13,18,29,34,35,39,41,43,45,46,47,57,64,68,71,73,74,75,78],
    ["2025255",5,13,15,21,25,26,27,31,37,39,46,50,54,56,57,59,65,70,78,79],
    ["2025254",16,18,20,29,32,36,37,41,52,53,54,55,56,57,65,69,70,74,75,76],
    ["2025253",3,10,20,23,27,30,32,35,44,48,50,51,53,56,57,63,65,68,70,72],
    ["2025252",13,18,19,26,27,30,33,37,41,43,47,49,53,58,61,64,68,71,73,76],
    ["2025251",1,2,4,14,15,23,25,26,27,30,36,39,42,44,46,52,55,62,65,66],
    ["2025250",1,2,6,16,20,21,23,26,27,29,30,34,40,43,59,63,65,71,79,80],
    # 2025302-2025351期开奖号码
    ["2025302",1,2,8,12,14,15,24,26,27,40,43,53,59,62,65,66,68,74,77,80],
    ["2025303",1,2,10,11,15,25,33,43,44,50,52,54,55,56,57,60,62,69,74,78],
    ["2025304",1,6,17,19,21,30,31,32,33,35,42,49,50,52,59,65,66,68,75,78],
    ["2025305",1,8,9,10,15,18,21,27,32,40,41,43,46,47,50,54,56,60,67,74],
    ["2025306",3,6,7,14,17,20,21,31,32,36,44,47,48,51,52,55,61,70,76,77],
    ["2025307",3,6,12,13,14,16,26,27,41,42,45,49,52,55,63,66,72,75,79,80],
    ["2025308",5,7,8,11,16,17,21,25,29,36,37,39,41,42,46,53,59,62,75,77],
    ["2025309",9,19,20,21,23,30,38,39,40,41,44,48,53,54,58,60,61,65,68,72],
    ["2025310",1,6,7,11,14,15,18,28,30,31,35,48,55,59,61,65,67,69,70,76],
    ["2025311",2,4,15,19,23,24,29,34,37,43,44,55,56,60,62,66,70,73,77,79],
    ["2025312",3,7,16,17,18,19,23,24,26,29,30,37,43,48,57,62,67,72,79,80],
    ["2025313",1,7,22,23,28,29,31,37,43,49,53,55,57,63,64,69,73,76,79,80],
    ["2025314",5,14,15,16,39,40,41,43,44,48,49,53,57,58,60,63,73,76,79,80],
    ["2025315",3,6,8,9,10,14,15,19,23,26,38,40,47,58,61,68,69,74,75,80],
    ["2025316",6,9,16,17,18,20,28,31,33,42,53,54,55,57,60,62,65,67,72,75],
    ["2025317",1,9,10,14,17,21,29,31,36,38,41,44,55,56,58,62,67,68,74,79],
    ["2025318",1,4,15,17,26,27,30,31,36,37,40,41,47,53,54,62,66,74,75,78],
    ["2025319",2,7,8,10,11,21,26,27,28,29,39,46,48,59,61,62,74,77,78,79],
    ["2025320",1,3,8,12,16,17,20,22,25,27,30,32,46,48,52,53,55,62,65,78],
    ["2025321",7,13,14,15,16,18,19,33,35,40,48,52,54,66,69,71,72,74,75,76],
    ["2025322",1,5,6,10,11,17,22,25,28,34,36,39,41,47,57,62,65,71,73,76],
    ["2025323",1,13,18,19,22,24,35,40,44,45,50,51,53,54,57,63,69,71,73,75],
    ["2025324",9,13,20,26,28,32,39,42,43,46,47,49,50,60,61,62,63,64,66,79],
    ["2025325",5,8,10,15,16,17,19,22,26,34,37,41,47,55,57,62,63,65,67,75],
    ["2025326",7,17,22,24,27,28,37,41,42,49,51,53,57,58,69,73,76,77,79,80],
    ["2025327",6,7,10,15,16,17,19,21,22,25,27,35,36,40,44,45,47,56,62,74],
    ["2025328",1,4,6,10,13,27,28,31,38,48,53,58,60,61,68,71,73,74,77,79],
    ["2025329",2,4,10,11,15,17,18,23,26,27,30,33,41,48,52,54,55,59,60,69],
    ["2025330",11,16,17,27,30,31,33,34,37,38,39,44,50,55,58,61,63,70,71,74],
    ["2025331",5,6,7,8,14,18,22,23,25,31,40,52,59,63,71,72,73,76,77,79],
    ["2025332",2,5,6,8,10,16,26,27,35,40,48,49,54,56,57,58,61,72,73,79],
    ["2025333",4,9,11,16,19,20,22,24,28,32,33,37,38,41,46,49,66,71,72,74],
    ["2025334",2,3,8,16,18,24,30,32,33,35,36,42,49,54,63,64,72,74,77,78],
    ["2025335",2,5,13,14,16,17,27,34,39,45,48,50,55,57,58,60,74,76,78,79],
    ["2025336",1,6,8,10,11,13,20,26,27,29,41,43,54,55,59,61,62,71,76,80],
    ["2025337",3,6,8,10,16,20,28,32,33,43,46,48,49,53,60,68,69,76,77,78],
    ["2025338",2,3,9,11,14,25,28,29,34,36,38,39,49,50,58,68,69,71,77,78],
    ["2025339",3,6,7,9,14,19,25,26,31,32,35,36,37,38,60,62,66,67,68,75],
    ["2025340",1,9,14,15,16,20,21,24,29,31,40,45,46,47,49,63,65,68,71,74],
    ["2025341",4,8,9,11,15,19,21,23,24,25,26,37,38,43,45,46,52,63,64,74],
    ["2025342",5,6,10,22,25,33,41,42,53,55,58,59,60,63,66,70,71,73,77,80],
    ["2025343",4,11,23,26,29,30,33,35,44,46,49,50,55,56,58,60,62,65,69,80],
    ["2025344",1,4,6,11,12,20,23,26,30,33,37,40,44,50,52,53,67,68,72,73],
    ["2025345",6,10,11,12,14,19,30,32,35,38,39,41,43,45,46,48,61,67,76,79],
    ["2025346",3,6,8,13,14,23,25,26,28,30,33,38,40,41,42,48,51,56,68,69],
    ["2025347",3,10,11,14,17,20,22,28,34,40,45,46,48,51,55,56,67,71,72,73],
    ["2025348",2,19,20,22,24,25,30,33,35,39,41,49,53,54,55,60,63,66,75,80],
    ["2025349",7,8,18,20,22,23,28,40,41,43,45,47,48,51,53,58,64,67,78,80],
    ["2025350",1,5,6,20,24,30,32,33,35,36,37,38,40,52,55,62,64,70,72,76],
    ["2025351",5,12,14,17,19,21,24,25,31,32,39,42,46,49,50,52,57,63,68,72],
    # 2026001-2026015期开奖号码
    ["2026001",2,5,6,11,24,25,27,32,34,35,39,41,44,51,54,62,70,71,72,75],
    ["2026002",3,8,10,17,22,24,25,28,39,51,61,62,67,69,70,71,72,73,74,80],
    ["2026003",2,7,14,16,22,25,28,31,39,42,47,53,54,55,61,68,69,72,73,78],
    ["2026004",4,5,9,13,16,21,23,24,32,35,37,38,45,50,52,54,55,62,63,64],
    ["2026005",7,8,9,14,18,21,24,26,33,35,41,43,49,54,56,59,60,63,68,76],
    ["2026006",3,5,7,9,19,28,30,32,34,38,49,52,56,61,62,66,73,76,78,79],
    ["2026007",3,13,15,18,20,21,25,32,42,43,45,54,57,62,63,68,72,74,76,80],
    ["2026008",2,4,15,20,21,23,24,34,47,50,51,52,57,58,60,61,66,71,77,79],
    ["2026009",3,4,8,17,18,31,34,37,42,46,47,55,56,61,65,70,74,75,76,80],
    ["2026010",6,7,13,16,19,27,33,37,39,42,43,44,55,59,62,64,65,67,76,80],
    ["2026011",1,3,12,16,22,25,27,30,32,49,52,56,59,61,62,63,66,68,69,79],
    ["2026012",4,11,12,15,16,20,21,26,27,28,30,32,33,41,53,60,62,64,65,76],
    ["2026013",1,5,9,10,11,12,14,15,16,22,28,32,37,41,44,64,72,77,78,80],
    ["2026014",6,12,13,14,18,24,28,29,30,34,38,43,49,52,59,60,64,74,78,80],
    ["2026015",2,8,9,11,14,17,18,19,27,29,31,34,36,41,55,60,64,70,72,79]
]

# 数据持久化函数
def init_lottery_data():
    """初始化或加载基础号码库（优先云端，后本地）"""
    config = get_gist_config()
    
    if config['token']:
        cloud_df = cloud_load_lottery_data(config)
        if cloud_df is not None:
            cloud_df = cloud_df.sort_index(ascending=True)
            local_df = None
            if os.path.exists('lottery_data_v2.csv'):
                local_df = pd.read_csv('lottery_data_v2.csv', index_col='期号', dtype={'期号': str})
                local_df = local_df.sort_index(ascending=True)
            
            if local_df is not None:
                if len(cloud_df) >= len(local_df):
                    save_lottery_data(cloud_df)
                    return cloud_df
                else:
                    return local_df
            return cloud_df
    
    if not os.path.exists('lottery_data_v2.csv'):
        df = pd.DataFrame(INITIAL_DATA, columns=['期号'] + [f'第{i}位' for i in range(1, 21)])
        df['期号'] = df['期号'].astype(str)
        df.set_index('期号', inplace=True)
        df = df.sort_index(ascending=True)
        df.to_csv('lottery_data_v2.csv')
        return df
    else:
        df = pd.read_csv('lottery_data_v2.csv', index_col='期号', dtype={'期号': str})
        df = df.sort_index(ascending=True)
        return df

def save_lottery_data(df):
    """保存基础号码库到本地并同步云端"""
    df.to_csv('lottery_data_v2.csv')
    config = get_gist_config()
    if config['token']:
        with st.spinner('正在同步到云端...'):
            success, error = cloud_save_lottery_data(df, config)
            if success:
                save_gist_config(config)
                st.success('✅ 数据已成功保存到本地 lottery_data_v2.csv，并已同步到云端')
            else:
                st.warning(f'⚠️ 数据已保存到本地，但云端同步失败：{error}')
                st.info('请检查 GitHub Token 是否有效')
    else:
        st.success('✅ 数据已成功保存到本地 lottery_data_v2.csv')

def save_prediction(prediction_data, period):
    """保存预测方案到本地并同步云端"""
    if not os.path.exists('predictions'):
        os.makedirs('predictions')
    
    filename = f'predictions/{period}_prediction.json'
    
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        if existing_data.get('step5_core_pool') == prediction_data.get('step5_core_pool') and \
           existing_data.get('step6_combinations') == prediction_data.get('step6_combinations'):
            return filename
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(prediction_data, f, ensure_ascii=False, indent=2)
    
    sync_predictions_to_cloud()
    
    return filename

def sync_predictions_to_cloud():
    """同步预测数据到云端"""
    predictions = load_all_predictions()
    config = get_gist_config()
    if config['token']:
        success, error = cloud_save_predictions(predictions, config)
        if success:
            save_gist_config(config)
            return True, None
        return False, error
    return False, 'No token'

def load_all_predictions():
    """加载所有已保存的预测记录（优先本地）"""
    predictions = {}
    if os.path.exists('predictions'):
        for file in os.listdir('predictions'):
            if file.endswith('_prediction.json'):
                period = file.replace('_prediction.json', '')
                filepath = os.path.join('predictions', file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        predictions[period] = json.load(f)
                except:
                    pass
    return dict(sorted(predictions.items()))

def save_hit_rate(prediction_period, result_period, hit_rate_data):
    """保存命中率到本地并同步云端"""
    if not os.path.exists('hit_rates'):
        os.makedirs('hit_rates')
    key = f'{prediction_period}_{result_period}'
    filepath = os.path.join('hit_rates', f'{key}_hitrate.json')
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(hit_rate_data, f, ensure_ascii=False, indent=2)
    sync_hit_rates_to_cloud()
    return filepath

def sync_hit_rates_to_cloud():
    """同步命中率数据到云端"""
    hit_rates = load_all_hit_rates()
    config = get_gist_config()
    if config['token']:
        success, error = cloud_save_hit_rates(hit_rates, config)
        if success:
            save_gist_config(config)
            return True, None
        return False, error
    return False, 'No token'

def load_all_hit_rates():
    """加载所有已保存的命中率记录"""
    hit_rates = {}
    if os.path.exists('hit_rates'):
        for file in os.listdir('hit_rates'):
            if file.endswith('_hitrate.json'):
                filepath = os.path.join('hit_rates', file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        key = f"{data['prediction_period']}_{data['result_period']}"
                        hit_rates[key] = data
                except:
                    pass
    return dict(sorted(hit_rates.items(), key=lambda x: x[0], reverse=True))

# 加载数据到Session State（全局通用调用）
if 'lottery_data' not in st.session_state:
    st.session_state.lottery_data = init_lottery_data()

# ==================== 【模块2】侧边栏导航与全局状态 ====================
with st.sidebar:
    st.title('🎱 快乐8预测系统')
    st.divider()
    st.markdown('### 📊 系统状态')
    st.write(f'当前数据量：**{len(st.session_state.lottery_data)}** 期')
    st.write(f'最新期号：**{st.session_state.lottery_data.index[-1]}**')
    st.divider()
    st.markdown('### ☁️ 云端同步设置')
    
    config = get_gist_config()
    
    with st.expander('⚙️ GitHub Gist 配置', expanded=not bool(config['token'])):
        st.caption('用于将数据同步到 GitHub Gist，防止程序重启后数据丢失')
        
        token_input = st.text_input(
            'GitHub Personal Access Token',
            value=config['token'],
            type='password',
            help='需要创建 GitHub Personal Access Token，勾选 gist 权限'
        )
        
        if st.button('💾 保存 Token', use_container_width=True):
            if token_input:
                test_result, error = get_or_create_gist(
                    token_input,
                    'test_connection.txt',
                    'Connection test',
                    '快乐8预测系统-连接测试'
                )
                if test_result:
                    config['token'] = token_input
                    save_gist_config(config)
                    st.success('✅ Token 验证成功！')
                    st.rerun()
                else:
                    st.error(f'❌ Token 验证失败：{error}')
            else:
                st.warning('⚠️ 请输入 Token')
        
        with st.expander('📖 如何获取 GitHub Token？'):
            st.markdown('''
            **获取 GitHub Personal Access Token 步骤：**
            
            1. 登录 GitHub，点击右上角头像 → **Settings**
            2. 左侧菜单找到 **Developer settings**
            3. 点击 **Personal access tokens** → **Tokens (classic)**
            4. 点击 **Generate new token (classic)**
            5. 勾选权限：**gist**（允许创建和编辑 Gist）
            6. 设置有效期，点击生成
            7. 复制生成的 Token 并粘贴到上方输入框
            
            **注意：** Token 只会显示一次，请妥善保管！
            ''')
    
    if config['token']:
        st.success('✅ 云端同步已启用')
        
        with st.expander('📋 云端存储状态', expanded=False):
            st.write(f'号码库 Gist ID：{config["lottery_gist_id"][:8] + "..." if config["lottery_gist_id"] else "未设置"}')
            st.write(f'预测方案 Gist ID：{config["predictions_gist_id"][:8] + "..." if config["predictions_gist_id"] else "未设置"}')
            st.write(f'命中率 Gist ID：{config["hitrates_gist_id"][:8] + "..." if config["hitrates_gist_id"] else "未设置"}')
            
            col_sync1, col_sync2 = st.columns(2)
            with col_sync1:
                if st.button('🔄 手动同步', use_container_width=True):
                    with st.spinner('正在同步...'):
                        df = st.session_state.lottery_data
                        success1, _ = cloud_save_lottery_data(df, config)
                        success2, _ = cloud_save_predictions(load_all_predictions(), config)
                        success3, _ = cloud_save_hit_rates(load_all_hit_rates(), config)
                        if success1 and success2 and success3:
                            save_gist_config(config)
                            st.success('✅ 同步成功！')
                        else:
                            st.error('⚠️ 部分同步失败')
            
            with col_sync2:
                if st.button('📥 从云端恢复', use_container_width=True):
                    with st.spinner('正在从云端恢复...'):
                        cloud_df = cloud_load_lottery_data(config)
                        if cloud_df is not None:
                            st.session_state.lottery_data = cloud_df.sort_index(ascending=True)
                            save_lottery_data(st.session_state.lottery_data)
                            st.success('✅ 数据已从云端恢复！')
                            st.rerun()
                        else:
                            st.warning('⚠️ 云端暂无数据')
    
    st.divider()
    st.markdown('### 📝 开发日志')
    st.info('V3.1 已上线：新增 GitHub Gist 云端同步功能，数据从此不丢失！')

# ==================== 【模块3】主界面Tab布局 ====================
tabs = st.tabs([
    '📚 Tab 1 号码库管理',
    '📊 Tab 2 数据分析',
    '🔗 Tab 3 相随号数据（预留）',
    '🔍 Tab 4 深度复盘',
    '🎯 Tab 5 选号方案（预留）',
    '📈 Tab 6 正确率复盘（预留）',
    '📋 Tab 7 体系全流程 SOP',
    '🔮 Tab 8 预测结果',
    '⚙️ Tab 9 预留板块'
])

# ==================== 【Tab 1】号码库管理 ====================
with tabs[0]:
    st.header('📚 基础号码库管理')
    st.markdown('''<div style="background-color: #f0f2f6; padding: 16px; border-radius: 8px; margin-bottom: 20px;">
    <p style="font-size: 16px; line-height: 1.6;">全局通用调用的基础数据库，支持新增、修改、查看开奖号码。</p>
    <ul style="margin-top: 10px; font-size: 14px;">
    <li>✅ 支持查看历史开奖数据</li>
    <li>✅ 新增最新开奖号码</li>
    <li>✅ 修改历史开奖数据</li>
    <li>✅ 自动排序和数据持久化</li>
    </ul>
    </div>''', unsafe_allow_html=True)

    # 左右分栏布局
    col_left, col_right = st.columns([1, 1.5])
    
    # 左侧：新增和修改
    with col_left:
        # 1. 新增数据
        st.subheader('➕ 新增开奖号码')
        
        # 自动生成下一期期号
        def generate_next_period():
            if not st.session_state.lottery_data.empty:
                max_period = st.session_state.lottery_data.index[-1]
                # 解析期号：前4位是年份，后3位是期数
                year = int(max_period[:4])
                period_num = int(max_period[4:])
                # 假设每年最多150期，超过则进入下一年
                if period_num >= 150:
                    next_year = year + 1
                    next_period_num = 1
                else:
                    next_year = year
                    next_period_num = period_num + 1
                return f"{next_year}{next_period_num:03d}"
            else:
                # 默认起始期号
                return "2025001"
        
        next_period = generate_next_period()
        
        with st.form(key='add_form'):
            new_period = st.text_input('期号', value=next_period, placeholder='如 2025001', help='7位数字格式：年+期号')
            new_nums_input = st.text_input(
                '开奖号码',
                placeholder='20个号码，空格/逗号分隔',
                help='1-80之间，自动排序'
            )
            submit_button = st.form_submit_button('✅ 新增号码', type='primary', use_container_width=True)
            
            if submit_button:
                success = False
                error_msg = ''
                
                # 验证期号（7位数字格式）
                if not new_period:
                    error_msg = '❌ 请输入期号'
                elif not new_period.isdigit():
                    error_msg = '❌ 期号只能包含数字'
                elif len(new_period) != 7:
                    error_msg = '❌ 期号必须是7位数字（格式：年+期号，如2025001）'
                elif new_period in st.session_state.lottery_data.index:
                    error_msg = f'❌ 期号 {new_period} 已存在，请选择其他期号'
                else:
                    # 处理号码输入
                    try:
                        # 支持多种分隔符：空格、逗号、分号、换行等
                        cleaned_input = new_nums_input.replace(',', ' ').replace(';', ' ').replace('\n', ' ')
                        nums = [int(x.strip()) for x in cleaned_input.split() if x.strip()]
                        
                        if len(nums) == 0:
                            error_msg = '❌ 未检测到任何号码，请输入开奖号码'
                        elif len(nums) < 20:
                            error_msg = f'❌ 号码数量不足，当前输入 {len(nums)} 个，需要 20 个'
                        elif len(nums) > 20:
                            error_msg = f'❌ 号码数量超出，当前输入 {len(nums)} 个，需要 20 个'
                        else:
                            # 检查号码范围
                            out_of_range = [n for n in nums if n < 1 or n > 80]
                            if out_of_range:
                                error_msg = f'❌ 号码超出范围(1-80)：{", ".join(map(str, sorted(out_of_range)))}'
                            else:
                                # 检查重复号码
                                duplicates = []
                                seen = set()
                                for n in nums:
                                    if n in seen:
                                        duplicates.append(n)
                                    seen.add(n)
                                if duplicates:
                                    error_msg = f'❌ 存在重复号码：{", ".join(map(str, sorted(set(duplicates))))}'
                                else:
                                    # 一切正常，保存数据
                                    nums.sort()
                                    st.session_state.lottery_data.loc[new_period] = nums
                                    st.session_state.lottery_data = st.session_state.lottery_data.sort_index(ascending=True)
                                    save_lottery_data(st.session_state.lottery_data)
                                    success = True
                    except ValueError as e:
                        error_msg = f'❌ 输入包含无效字符：{str(e)}'
                
                if success:
                    st.success(f'✅ 期号 {new_period} 添加成功！')
                    st.info(f'号码已自动排序：{" ".join(map(str, nums))}')
                    if len(st.session_state.lottery_data) >= 10:
                        st.session_state['auto_run_sop'] = True
                    st.rerun()
                else:
                    st.error(error_msg)

        st.divider()

        # 2. 修改数据
        st.subheader('✏️ 修改开奖号码')
        period_list = st.session_state.lottery_data.index.tolist() if len(st.session_state.lottery_data) > 0 else []
        if period_list:
            with st.form(key='modify_form'):
                modify_period = st.selectbox('选择期号', period_list, index=len(period_list)-1)
                current_nums = st.session_state.lottery_data.loc[modify_period].tolist()
                modify_nums_input = st.text_input(
                    '开奖号码',
                    value=' '.join(map(str, current_nums)),
                    placeholder='20个号码，空格/逗号分隔'
                )
                submit_button = st.form_submit_button('✅ 修改号码', type='primary', use_container_width=True)
                
                if submit_button:
                    try:
                        nums = [int(x.strip()) for x in modify_nums_input.replace(',', ' ').split() if x.strip()]
                        if len(nums) != 20:
                            st.error(f'❌ 请输入20个号码')
                        elif any(n < 1 or n > 80 for n in nums):
                            st.error('❌ 号码必须在1-80之间')
                        elif len(nums) != len(set(nums)):
                            st.error('❌ 号码不能重复')
                        else:
                            nums.sort()
                            st.session_state.lottery_data.loc[modify_period] = nums
                            save_lottery_data(st.session_state.lottery_data)
                            st.success('✅ 修改成功！')
                            st.rerun()
                    except ValueError:
                        st.error('❌ 请输入有效数字')
        else:
            st.info('暂无数据，请先添加')

        st.divider()

        # 3. 删除数据
        st.subheader('🗑️ 删除开奖号码')
        delete_period_list = st.session_state.lottery_data.index.tolist() if len(st.session_state.lottery_data) > 0 else []
        if delete_period_list:
            with st.form(key='delete_form'):
                delete_period = st.selectbox('选择要删除的期号', delete_period_list, index=len(delete_period_list)-1)
                confirm_checkbox = st.checkbox(f'确认删除期号 {delete_period}')
                submit_button = st.form_submit_button('🗑️ 删除号码', use_container_width=True)
                
                if submit_button:
                    if confirm_checkbox:
                        st.session_state.lottery_data = st.session_state.lottery_data.drop(delete_period)
                        save_lottery_data(st.session_state.lottery_data)
                        st.success(f'✅ 期号 {delete_period} 删除成功！')
                        st.rerun()
                    else:
                        st.error('❌ 请先勾选确认框')
        else:
            st.info('暂无数据可删除')

    # 右侧：查看已有的号码
    with col_right:
        st.subheader('📋 开奖号码列表')
        
        # 重新获取最新的期号列表
        display_period_list = st.session_state.lottery_data.index.tolist() if len(st.session_state.lottery_data) > 0 else []
        
        # 筛选和搜索
        col_filter1, col_filter2 = st.columns([1, 2])
        with col_filter1:
            quick_range = st.selectbox('快速选择', ['全部', '最近10期', '最近20期', '最近30期'], index=1)
        with col_filter2:
            search_period = st.text_input('搜索期号', placeholder='输入关键词')
        
        if display_period_list:
            # 快捷范围选择
            if quick_range == '最近10期':
                filtered_periods = display_period_list[-10:]
            elif quick_range == '最近20期':
                filtered_periods = display_period_list[-20:]
            elif quick_range == '最近30期':
                filtered_periods = display_period_list[-30:]
            else:
                filtered_periods = display_period_list
            
            # 搜索过滤
            if search_period:
                filtered_periods = [p for p in filtered_periods if search_period in p]
            
            # 倒序显示
            filtered_periods.reverse()
            
            # 统计信息
            st.markdown(f'''
            <div style="display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap;">
            <span style="background-color: #e3f2fd; padding: 6px 12px; border-radius: 4px; font-size: 12px;">📊 总期数: {len(st.session_state.lottery_data)}</span>
            <span style="background-color: #e8f5e8; padding: 6px 12px; border-radius: 4px; font-size: 12px;">🔢 当前: {len(filtered_periods)}期</span>
            <span style="background-color: #fff3e0; padding: 6px 12px; border-radius: 4px; font-size: 12px;">🆕 最新: {st.session_state.lottery_data.index[-1]}</span>
            </div>
            ''', unsafe_allow_html=True)
            
            # 紧凑卡片显示
            for period in filtered_periods:
                nums = st.session_state.lottery_data.loc[period].tolist()
                nums_str = ' '.join(f'{n:02d}' for n in nums)
                
                st.markdown(f'''
                <div style="background-color: #f8f9fa; padding: 10px 14px; border-radius: 5px; margin-bottom: 6px;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                <span style="font-weight: bold; color: #1565c0; font-size: 13px;">{period}</span>
                <span style="font-family: monospace; font-size: 12px; color: #333;">{nums_str}</span>
                </div>
                </div>
                ''', unsafe_allow_html=True)
        else:
            st.info('暂无数据，请在左侧添加')

# ==================== 【Tab 2】数据分析 ====================
with tabs[1]:
    st.header('📊 多周期数据分析')
    st.markdown('调用号码库数据，进行多维度统计分析。')
    st.divider()

    # 1. 周期选择
    period_options = [150, 100, 80, 50, 20, 10, 5]
    selected_period = st.selectbox(
        '请选择分析周期',
        period_options,
        index=3,
        help='选择要分析的最近N期数据'
    )

    # 获取最近N期数据
    data = st.session_state.lottery_data
    if len(data) >= selected_period:
        recent_data = data.tail(selected_period)
    else:
        recent_data = data
        st.warning(f'⚠️ 数据不足 {selected_period} 期，仅分析现有 {len(recent_data)} 期')

    # 2. 统计所有号码出现次数
    all_numbers = []
    for col in recent_data.columns:
        all_numbers.extend(recent_data[col].dropna().astype(int).tolist())
    
    number_counts = pd.Series(all_numbers).value_counts().reindex(range(1, 81), fill_value=0).sort_index()
    number_counts_df = number_counts.rename('出现次数').to_frame()
    number_counts_df['排名'] = number_counts_df['出现次数'].rank(ascending=False, method='min').astype(int)

    # 3. 展示出现次数统计
    st.subheader(f'📌 近 {selected_period} 期号码出现次数')
    col_stat1, col_stat2 = st.columns([3, 1])
    with col_stat1:
        st.bar_chart(number_counts, color='#FF4B4B')
    with col_stat2:
        st.dataframe(
            number_counts_df[['排名', '出现次数']].sort_values('排名'),
            use_container_width=True,
            height=400
        )

    # 4. 冷热温号判定
    st.divider()
    st.subheader('🔥 冷热温号判定')
    st.caption('判定规则：热号（前20%）、温号（中间60%）、冷号（后20%）')
    
    # 过滤掉未出现的号码（避免分位数偏差）
    valid_counts = number_counts[number_counts > 0]
    if len(valid_counts) > 0:
        hot_thresh = valid_counts.quantile(0.8)
        cold_thresh = valid_counts.quantile(0.2)
        
        hot_nums = number_counts[number_counts >= hot_thresh].index.tolist()
        cold_nums = number_counts[number_counts <= cold_thresh].index.tolist()
        warm_nums = number_counts[(number_counts > cold_thresh) & (number_counts < hot_thresh)].index.tolist()
        
        col_hot, col_warm, col_cold = st.columns(3)
        with col_hot:
            st.markdown('''<div style="background-color: #ffebee; padding: 16px; border-radius: 8px;">
            <h4 style="color: #c62828; margin-top: 0;">🔥 热号 <span style="font-size: 14px; font-weight: normal;">({}个)</span></h4>
            <p style="font-size: 12px; color: #757575;">出现次数 ≥ {:.1f}</p>
            <p style="font-family: monospace; font-size: 14px; color: #c62828; line-height: 1.6;">{}</p>
            </div>'''.format(len(hot_nums), hot_thresh, ' '.join(f'<span style="color: #c62828; font-weight: bold;">{n:02d}</span>' for n in sorted(hot_nums))), unsafe_allow_html=True)
        with col_warm:
            st.markdown('''<div style="background-color: #fff8e1; padding: 16px; border-radius: 8px;">
            <h4 style="color: #f57c00; margin-top: 0;">🌡️ 温号 <span style="font-size: 14px; font-weight: normal;">({}个)</span></h4>
            <p style="font-size: 12px; color: #757575;">出现次数 {:.1f} ~ {:.1f}</p>
            <p style="font-family: monospace; font-size: 14px; color: #f57c00; line-height: 1.6;">{}</p>
            </div>'''.format(len(warm_nums), cold_thresh, hot_thresh, ' '.join(f'<span style="color: #f57c00;">{n:02d}</span>' for n in sorted(warm_nums))), unsafe_allow_html=True)
        with col_cold:
            st.markdown('''<div style="background-color: #e3f2fd; padding: 16px; border-radius: 8px;">
            <h4 style="color: #1565c0; margin-top: 0;">❄️ 冷号 <span style="font-size: 14px; font-weight: normal;">({}个)</span></h4>
            <p style="font-size: 12px; color: #757575;">出现次数 ≤ {:.1f}</p>
            <p style="font-family: monospace; font-size: 14px; color: #1565c0; line-height: 1.6;">{}</p>
            </div>'''.format(len(cold_nums), cold_thresh, ' '.join(f'<span style="color: #1565c0; font-weight: bold;">{n:02d}</span>' for n in sorted(cold_nums))), unsafe_allow_html=True)

    # 5. 012 路统计
    st.divider()
    st.subheader('🔢 012 路统计')
    road_counts = defaultdict(int)
    for num in all_numbers:
        road = num % 3
        road_counts[road] += 1
    
    road_df = pd.DataFrame({
        '路数': ['0路（除3余0）', '1路（除3余1）', '2路（除3余2）'],
        '出现次数': [road_counts[0], road_counts[1], road_counts[2]],
        '占比': [
            f"{road_counts[0]/len(all_numbers)*100:.1f}%",
            f"{road_counts[1]/len(all_numbers)*100:.1f}%",
            f"{road_counts[2]/len(all_numbers)*100:.1f}%"
        ]
    }).set_index('路数')
    
    col_road1, col_road2 = st.columns([2, 1])
    with col_road1:
        st.bar_chart(road_df['出现次数'], color=['#FF9F43'])
    with col_road2:
        st.dataframe(road_df, use_container_width=True)

# ==================== 【Tab 3】相随号数据 ====================
with tabs[2]:
    st.header('🔗 相随号数据')
    st.markdown('基于号码库数据，分析号码之间的相随关系和同频组合。')
    st.divider()
    
    # 周期选择
    period_options = [150, 100, 80, 50, 30, 20, 10]
    selected_period = st.selectbox(
        '请选择分析周期',
        period_options,
        index=3,
        help='选择要分析的最近N期数据'
    )
    
    data = st.session_state.lottery_data
    if len(data) >= selected_period:
        recent_data = data.tail(selected_period)
    else:
        recent_data = data
        st.warning(f'⚠️ 数据不足 {selected_period} 期，仅分析现有 {len(recent_data)} 期')
    
    # 1. 相随号分析
    st.subheader('� 相随号分析')
    st.caption('相随号定义：N期开出的号码A，N+1期跟着开出的号码')
    
    # 构建相随号字典
    follow_dict = defaultdict(list)
    periods = recent_data.index.tolist()
    
    for i in range(len(periods) - 1):
        current_nums = set(recent_data.loc[periods[i]].dropna().astype(int).tolist())
        next_nums = set(recent_data.loc[periods[i+1]].dropna().astype(int).tolist())
        
        for num in current_nums:
            follow_dict[num].extend(list(next_nums))
    
    # 统计每个号码的相随号频率并取前5
    follow_top5 = {}
    for num, follows in follow_dict.items():
        freq = pd.Series(follows).value_counts()
        follow_top5[num] = freq.head(5).to_dict()
    
    # 展示相随号
    col_follow1, col_follow2 = st.columns([1, 2])
    with col_follow1:
        selected_num = st.selectbox('选择号码查看相随号', sorted(follow_top5.keys()), index=0)
    with col_follow2:
        if selected_num in follow_top5:
            st.markdown(f'''<div style="background-color: #e3f2fd; padding: 16px; border-radius: 8px;">
            <h4 style="color: #1565c0; margin-top: 0;">🔗 号码 {selected_num:02d} 的相随号（前5名）</h4>
            <div style="margin-top: 10px;">
            {''.join([f'<div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #b3d9f5;">\n<span style="font-weight: bold; color: #1565c0;">{k:02d}</span>\n<span style="color: #666;">出现 {v} 次</span>\n</div>' for k, v in follow_top5[selected_num].items()])}
            </div>
            </div>''', unsafe_allow_html=True)
    
    st.divider()
    
    # 2. 同频双码分析
    st.subheader('📊 同频双码')
    st.caption('同频双码：同一期出现的两个号码组合')
    
    pair_counts = defaultdict(int)
    for idx, row in recent_data.iterrows():
        nums = row.dropna().astype(int).tolist()
        for i in range(len(nums)):
            for j in range(i+1, len(nums)):
                pair = tuple(sorted([nums[i], nums[j]]))
                pair_counts[pair] += 1
    
    # 取出现次数最多的前20对
    top_pairs = sorted(pair_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    
    st.markdown('''<div style="background-color: #f5f5f5; padding: 16px; border-radius: 8px;">
    <h4 style="margin-top: 0; color: #333;">🔥 出现次数最多的双码组合（前20）</h4>
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 8px; margin-top: 12px;">
    {}</div>
    </div>'''.format(''.join([f'<div style="background-color: #fff; padding: 8px; border-radius: 4px; text-align: center; border: 1px solid #ddd;">\n<span style="font-family: monospace; font-weight: bold; color: #c62828;">{p[0][0]:02d}-{p[0][1]:02d}</span>\n<br/>\n<span style="font-size: 12px; color: #666;">{p[1]}次</span>\n</div>' for p in top_pairs])), unsafe_allow_html=True)
    
    st.divider()
    
    # 3. 同频三码分析
    st.subheader('📊 同频三码')
    st.caption('同频三码：同一期出现的三个号码组合')
    
    triplet_counts = defaultdict(int)
    for idx, row in recent_data.iterrows():
        nums = row.dropna().astype(int).tolist()
        for i in range(len(nums)):
            for j in range(i+1, len(nums)):
                for k in range(j+1, len(nums)):
                    triplet = tuple(sorted([nums[i], nums[j], nums[k]]))
                    triplet_counts[triplet] += 1
    
    # 取出现次数最多的前15组
    top_triplets = sorted(triplet_counts.items(), key=lambda x: x[1], reverse=True)[:15]
    
    st.markdown('''<div style="background-color: #f5f5f5; padding: 16px; border-radius: 8px;">
    <h4 style="margin-top: 0; color: #333;">🔥 出现次数最多的三码组合（前15）</h4>
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; margin-top: 12px;">
    {}</div>
    </div>'''.format(''.join([f'<div style="background-color: #fff; padding: 8px; border-radius: 4px; text-align: center; border: 1px solid #ddd;">\n<span style="font-family: monospace; font-weight: bold; color: #1565c0;">{t[0][0]:02d}-{t[0][1]:02d}-{t[0][2]:02d}</span>\n<br/>\n<span style="font-size: 12px; color: #666;">{t[1]}次</span>\n</div>' for t in top_triplets])), unsafe_allow_html=True)

# ==================== 【Tab 4】深度复盘 ====================
with tabs[3]:
    st.header('🔍 深度复盘与对比')
    st.markdown('选择 N 期进行复盘，并调取 N-1 期数据进行对比。')
    st.divider()

    if len(st.session_state.lottery_data) >= 2:
        period_list = st.session_state.lottery_data.index.tolist()
        
        # 选择 N 期
        n_period = st.selectbox(
            '请选择 N 期',
            period_list[1:],
            index=len(period_list)-2,
            help='选择要复盘的期号'
        )
        n_idx = period_list.index(n_period)
        n_minus_1_period = period_list[n_idx - 1]
        
        # 展示两期数据
        col_n, col_n1 = st.columns(2)
        with col_n:
            st.subheader(f'📅 {n_period} 期开奖号码')
            n_nums = st.session_state.lottery_data.loc[n_period].dropna().astype(int).tolist()
            st.write(f'**升序排列**：{sorted(n_nums)}')
            st.write(f'**奇偶比**：{sum(1 for x in n_nums if x%2==1)} : {sum(1 for x in n_nums if x%2==0)}')
            st.write(f'**012路**：0路{sum(1 for x in n_nums if x%3==0)}个，1路{sum(1 for x in n_nums if x%3==1)}个，2路{sum(1 for x in n_nums if x%3==2)}个')
        with col_n1:
            st.subheader(f'📅 {n_minus_1_period} 期开奖号码')
            n1_nums = st.session_state.lottery_data.loc[n_minus_1_period].dropna().astype(int).tolist()
            st.write(f'**升序排列**：{sorted(n1_nums)}')
            st.write(f'**奇偶比**：{sum(1 for x in n1_nums if x%2==1)} : {sum(1 for x in n1_nums if x%2==0)}')
            st.write(f'**012路**：0路{sum(1 for x in n1_nums if x%3==0)}个，1路{sum(1 for x in n1_nums if x%3==1)}个，2路{sum(1 for x in n1_nums if x%3==2)}个')
        
        # 对比分析
        st.divider()
        st.subheader('📊 两期对比分析')
        overlap = set(n_nums) & set(n1_nums)
        col_overlap, col_diff = st.columns(2)
        with col_overlap:
            st.metric('重合号码数量', len(overlap))
            st.write(f'**重合号码**：{sorted(list(overlap))}')
        with col_diff:
            st.metric('新增号码数量', 20 - len(overlap))
            st.write(f'**新增号码**：{sorted(list(set(n_nums) - overlap))}')
    else:
        st.warning('⚠️ 数据不足 2 期，无法进行对比')

# ==================== 【Tab 5】预测复盘对比 ====================
with tabs[4]:
    st.header('🎯 预测复盘对比')
    st.divider()
    
    # 加载所有已保存的预测记录
    predictions = load_all_predictions()
    # 获取 Tab 1 号码库中的期号列表
    period_list = st.session_state.lottery_data.index.tolist() if len(st.session_state.lottery_data) > 0 else []
    
    if predictions and period_list:
        col1, col2 = st.columns(2)
        
        with col1:
            # 预测期号（从保存的预测记录中选择）
            pred_period_list = list(predictions.keys())
            pred_period = st.selectbox('预测期号', pred_period_list, index=len(pred_period_list)-1)
        
        with col2:
            # 开奖期号（从号码库选择）
            selected_period = st.selectbox('开奖期号', period_list, index=len(period_list)-1)
        
        # 获取预测数据
        pred = predictions[pred_period]
        core_pool_str = pred['core_pool']
        combinations = pred['combinations']
        
        # 获取开奖号码
        winning_numbers = st.session_state.lottery_data.loc[selected_period].tolist()
        winning_numbers_str = ' '.join(map(str, sorted(winning_numbers)))
        
        # 显示期号对应关系
        st.markdown(f'''<div style="background-color: #e3f2fd; padding: 16px; border-radius: 8px; margin-bottom: 12px;"><h4 style="margin-top: 0; color: #1565c0;">{pred_period}期预测号码库 vs {selected_period}期开奖结果</h4></div>''', unsafe_allow_html=True)
        
        col_result1, col_result2 = st.columns(2)
        with col_result1:
            st.markdown('''<div style="background-color: #f5f5f5; padding: 12px; border-radius: 6px;"><h4 style="margin-top: 0;">预测号码</h4><p style="font-family: monospace; font-size: 14px;">{}</p></div>'''.format(core_pool_str), unsafe_allow_html=True)
        with col_result2:
            st.markdown('''<div style="background-color: #f5f5f5; padding: 12px; border-radius: 6px;"><h4 style="margin-top: 0;">开奖号码</h4><p style="font-family: monospace; font-size: 14px;">{}</p></div>'''.format(winning_numbers_str), unsafe_allow_html=True)
        
        # 获取预测号码
        predicted_numbers = [int(x) for x in core_pool_str.split()]
        
        # 找出正确的号码
        correct_numbers = [num for num in predicted_numbers if num in winning_numbers]
        
        # 显示正确号码（红色）
        correct_str = ' '.join([f'<span style="color: #c62828; font-weight: bold;">{num}</span>' for num in sorted(correct_numbers)]) if correct_numbers else '无'
        st.markdown(f'''<div style="background-color: #ffebee; padding: 12px; border-radius: 6px; margin-top: 12px;"><h4 style="margin-top: 0; color: #c62828;">命中号码（{len(correct_numbers)}/{len(predicted_numbers)}）</h4><p style="font-family: monospace; font-size: 14px;">{correct_str}</p></div>''', unsafe_allow_html=True)
        
        # 组合打法对比
        st.subheader('📌 组合打法命中情况')
        
        # 收集组合命中数据
        combo_hit_data = {
            'eight_code': [],
            'six_code': [],
            'three_code': []
        }
        
        tab_8, tab_6, tab_3 = st.tabs(['10组8码', '10组6码', '10组3码'])
        with tab_8:
            eight_code = combinations['eight_code']
            col_8_1, col_8_2 = st.columns(2)
            for i, comb in enumerate(eight_code, 1):
                display_nums = []
                hit_count = 0
                for num in comb:
                    if num in winning_numbers:
                        display_nums.append(f'<span style="color: #c62828; font-weight: bold;">{num}</span>')
                        hit_count += 1
                    else:
                        display_nums.append(str(num))
                result = ' '.join(display_nums)
                bg_color = '#ffebee' if hit_count >= 4 else '#f5f5f5'
                combo_hit_data['eight_code'].append({
                    'index': i,
                    'numbers': comb,
                    'hit_count': hit_count,
                    'hit_numbers': [num for num in comb if num in winning_numbers]
                })
                if i <= 5:
                    with col_8_1:
                        st.markdown('''<div style="background-color: {}; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">8-{:02d}</span>（命中{}个）：{}</div>'''.format(bg_color, i, hit_count, result), unsafe_allow_html=True)
                else:
                    with col_8_2:
                        st.markdown('''<div style="background-color: {}; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">8-{:02d}</span>（命中{}个）：{}</div>'''.format(bg_color, i, hit_count, result), unsafe_allow_html=True)
        
        with tab_6:
            six_code = combinations['six_code']
            col_6_1, col_6_2 = st.columns(2)
            for i, comb in enumerate(six_code, 1):
                display_nums = []
                hit_count = 0
                for num in comb:
                    if num in winning_numbers:
                        display_nums.append(f'<span style="color: #c62828; font-weight: bold;">{num}</span>')
                        hit_count += 1
                    else:
                        display_nums.append(str(num))
                result = ' '.join(display_nums)
                bg_color = '#ffebee' if hit_count >= 3 else '#f5f5f5'
                combo_hit_data['six_code'].append({
                    'index': i,
                    'numbers': comb,
                    'hit_count': hit_count,
                    'hit_numbers': [num for num in comb if num in winning_numbers]
                })
                if i <= 5:
                    with col_6_1:
                        st.markdown('''<div style="background-color: {}; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">6-{:02d}</span>（命中{}个）：{}</div>'''.format(bg_color, i, hit_count, result), unsafe_allow_html=True)
                else:
                    with col_6_2:
                        st.markdown('''<div style="background-color: {}; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">6-{:02d}</span>（命中{}个）：{}</div>'''.format(bg_color, i, hit_count, result), unsafe_allow_html=True)
        
        with tab_3:
            three_code = combinations['three_code']
            col_3_1, col_3_2 = st.columns(2)
            for i, comb in enumerate(three_code, 1):
                display_nums = []
                hit_count = 0
                for num in comb:
                    if num in winning_numbers:
                        display_nums.append(f'<span style="color: #c62828; font-weight: bold;">{num}</span>')
                        hit_count += 1
                    else:
                        display_nums.append(str(num))
                result = ' '.join(display_nums)
                bg_color = '#ffebee' if hit_count >= 2 else '#f5f5f5'
                combo_hit_data['three_code'].append({
                    'index': i,
                    'numbers': comb,
                    'hit_count': hit_count,
                    'hit_numbers': [num for num in comb if num in winning_numbers]
                })
                if i <= 5:
                    with col_3_1:
                        st.markdown('''<div style="background-color: {}; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">3-{:02d}</span>（命中{}个）：{}</div>'''.format(bg_color, i, hit_count, result), unsafe_allow_html=True)
                else:
                    with col_3_2:
                        st.markdown('''<div style="background-color: {}; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">3-{:02d}</span>（命中{}个）：{}</div>'''.format(bg_color, i, hit_count, result), unsafe_allow_html=True)
        
        st.divider()
        st.subheader('📊 本次对比总结')
        
        # 计算总结数据
        core_hit_count = len(correct_numbers)
        core_total = len(predicted_numbers)
        core_hit_rate = (core_hit_count / core_total * 100) if core_total > 0 else 0
        
        # 8码最佳命中
        eight_best = max(combo_hit_data['eight_code'], key=lambda x: x['hit_count'])
        # 6码最佳命中
        six_best = max(combo_hit_data['six_code'], key=lambda x: x['hit_count'])
        # 3码最佳命中
        three_best = max(combo_hit_data['three_code'], key=lambda x: x['hit_count'])
        
        # 显示总结卡片
        col_summary1, col_summary2 = st.columns(2)
        
        with col_summary1:
            st.markdown(f'''
            <div style="background-color: #e3f2fd; padding: 16px; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #1565c0;">核心池命中率</h4>
                <p style="font-size: 24px; font-weight: bold; color: #c62828;">{core_hit_count}/{core_total} ({core_hit_rate:.1f}%)</p>
                <p style="margin-bottom: 0;">命中号码：{', '.join(map(str, sorted(correct_numbers))) if correct_numbers else '无'}</p>
            </div>
            ''', unsafe_allow_html=True)
        
        with col_summary2:
            st.markdown(f'''
            <div style="background-color: #fff3e0; padding: 16px; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #ef6c00;">最佳单组命中</h4>
                <p>8码最佳：8-{eight_best['index']:02d} 命中{eight_best['hit_count']}个</p>
                <p>6码最佳：6-{six_best['index']:02d} 命中{six_best['hit_count']}个</p>
                <p>3码最佳：3-{three_best['index']:02d} 命中{three_best['hit_count']}个</p>
            </div>
            ''', unsafe_allow_html=True)
        
        # 存档按钮
        st.divider()
        if st.button('💾 保存本次命中率记录', type='primary'):
            # 构建存档数据
            hit_rate_data = {
                'prediction_period': pred_period,
                'result_period': selected_period,
                'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'core_pool': core_pool_str,
                'winning_numbers': winning_numbers_str,
                'core_hit_count': core_hit_count,
                'core_total': core_total,
                'core_hit_rate': core_hit_rate,
                'combinations': combo_hit_data
            }
            # 保存
            filepath = save_hit_rate(pred_period, selected_period, hit_rate_data)
            st.success(f'✅ 命中率记录已保存到：{filepath}')
    else:
        if not predictions:
            st.warning('⚠️ 暂无预测记录，请先在 Tab 7 中执行 SOP 流程')
        if not period_list:
            st.warning('⚠️ 暂无开奖数据，请先在 Tab 1 中添加')

# ==================== 【Tab 6】正确率复盘 ====================
with tabs[5]:
    st.header('📈 正确率复盘')
    st.divider()
    
    hit_rates = load_all_hit_rates()
    
    if hit_rates:
        # ==================== 命中率统计板块 ====================
        st.subheader('📊 命中率统计')
        
        # 计算整体统计数据
        total_records = len(hit_rates)
        core_hit_rates = [hr['core_hit_rate'] for hr in hit_rates.values()]
        avg_hit_rate = sum(core_hit_rates) / total_records if total_records > 0 else 0
        max_hit_rate = max(core_hit_rates) if core_hit_rates else 0
        min_hit_rate = min(core_hit_rates) if core_hit_rates else 0
        
        # 统计核心池命中数量分布
        hit_counts = [hr['core_hit_count'] for hr in hit_rates.values()]
        hit_counts_dist = Counter(hit_counts)
        
        # 统计8码、6码、3码中奖个数的次数分布
        eight_hit_dist = Counter()
        six_hit_dist = Counter()
        three_hit_dist = Counter()
        
        for hr in hit_rates.values():
            # 统计8码所有组合的命中次数分布
            for combo in hr['combinations']['eight_code']:
                eight_hit_dist[combo['hit_count']] += 1
            # 统计6码所有组合的命中次数分布
            for combo in hr['combinations']['six_code']:
                six_hit_dist[combo['hit_count']] += 1
            # 统计3码所有组合的命中次数分布
            for combo in hr['combinations']['three_code']:
                three_hit_dist[combo['hit_count']] += 1
        
        # 计算组合最佳命中统计
        eight_max_hits = []
        six_max_hits = []
        three_max_hits = []
        
        for hr in hit_rates.values():
            eight_best = max(hr['combinations']['eight_code'], key=lambda x: x['hit_count'])['hit_count']
            six_best = max(hr['combinations']['six_code'], key=lambda x: x['hit_count'])['hit_count']
            three_best = max(hr['combinations']['three_code'], key=lambda x: x['hit_count'])['hit_count']
            eight_max_hits.append(eight_best)
            six_max_hits.append(six_best)
            three_max_hits.append(three_best)
        
        avg_eight_hit = sum(eight_max_hits) / len(eight_max_hits) if eight_max_hits else 0
        avg_six_hit = sum(six_max_hits) / len(six_max_hits) if six_max_hits else 0
        avg_three_hit = sum(three_max_hits) / len(three_max_hits) if three_max_hits else 0
        
        # 显示统计卡片（第一行）
        col_stats1, col_stats2, col_stats3 = st.columns(3)
        with col_stats1:
            st.markdown(f'''
            <div style="background-color: #e3f2fd; padding: 16px; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #1565c0;">📊 统计概览</h4>
                <p style="font-size: 20px; font-weight: bold;">共 {total_records} 条记录</p>
                <p>平均命中率：{avg_hit_rate:.1f}%</p>
                <p>最高命中率：{max_hit_rate:.1f}%</p>
                <p>最低命中率：{min_hit_rate:.1f}%</p>
            </div>
            ''', unsafe_allow_html=True)
        
        with col_stats2:
            st.markdown(f'''
            <div style="background-color: #e8f5e8; padding: 16px; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #2e7d32;">🎯 组合最佳命中</h4>
                <p style="font-size: 16px; font-weight: bold;">平均最佳命中</p>
                <p>8码：{avg_eight_hit:.1f} 个</p>
                <p>6码：{avg_six_hit:.1f} 个</p>
                <p>3码：{avg_three_hit:.1f} 个</p>
            </div>
            ''', unsafe_allow_html=True)
        
        with col_stats3:
            st.markdown(f'''
            <div style="background-color: #fff3e0; padding: 16px; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #ef6c00;">📈 核心池命中分布</h4>
                <p style="font-size: 14px;">命中数量统计</p>
                {''.join([f'<p>{k}个: {v}次 ({v/total_records*100:.0f}%)</p>' for k, v in sorted(hit_counts_dist.items())])}
            </div>
            ''', unsafe_allow_html=True)
        
        # 显示8码、6码、3码中奖个数的次数分布（第二行）
        st.divider()
        st.subheader('🎯 组合命中次数分布')
        
        col_eight, col_six, col_three = st.columns(3)
        
        with col_eight:
            st.markdown(f'''
            <div style="background-color: #ffebee; padding: 16px; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #c62828;">🔥 8码命中分布</h4>
                <p style="font-size: 14px;">各命中个数出现次数</p>
                {''.join([f'<p>{k}个: {v}次</p>' for k, v in sorted(eight_hit_dist.items())])}
            </div>
            ''', unsafe_allow_html=True)
        
        with col_six:
            st.markdown(f'''
            <div style="background-color: #fff3e0; padding: 16px; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #ef6c00;">🌡️ 6码命中分布</h4>
                <p style="font-size: 14px;">各命中个数出现次数</p>
                {''.join([f'<p>{k}个: {v}次</p>' for k, v in sorted(six_hit_dist.items())])}
            </div>
            ''', unsafe_allow_html=True)
        
        with col_three:
            st.markdown(f'''
            <div style="background-color: #e3f2fd; padding: 16px; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #1565c0;">💧 3码命中分布</h4>
                <p style="font-size: 14px;">各命中个数出现次数</p>
                {''.join([f'<p>{k}个: {v}次</p>' for k, v in sorted(three_hit_dist.items())])}
            </div>
            ''', unsafe_allow_html=True)
        
        st.divider()
        
        # ==================== 原有代码 ====================
        st.subheader('📑 所有命中率记录概览')
        
        overview_data = []
        for key, hr in hit_rates.items():
            eight_max = max(hr['combinations']['eight_code'], key=lambda x: x['hit_count'])['hit_count']
            eight_best_groups = [f"8-{c['index']:02d}" for c in hr['combinations']['eight_code'] if c['hit_count'] == eight_max]
            
            six_max = max(hr['combinations']['six_code'], key=lambda x: x['hit_count'])['hit_count']
            six_best_groups = [f"6-{c['index']:02d}" for c in hr['combinations']['six_code'] if c['hit_count'] == six_max]
            
            three_max = max(hr['combinations']['three_code'], key=lambda x: x['hit_count'])['hit_count']
            three_best_groups = [f"3-{c['index']:02d}" for c in hr['combinations']['three_code'] if c['hit_count'] == three_max]
            
            overview_data.append({
                '预测期': hr['prediction_period'],
                '开奖期': hr['result_period'],
                '核心命中': f"{hr['core_hit_count']}/{hr['core_total']}",
                '命中率(%)': round(hr['core_hit_rate'], 1),
                '最佳8码': f"{', '.join(eight_best_groups)} ({eight_max}个)",
                '最佳6码': f"{', '.join(six_best_groups)} ({six_max}个)",
                '最佳3码': f"{', '.join(three_best_groups)} ({three_max}个)",
                '保存时间': hr['saved_at']
            })
        
        if overview_data:
            df = pd.DataFrame(overview_data)
            st.dataframe(df, use_container_width=True)
        
        # 选择记录查看详情
        st.subheader('📊 详细命中记录')
        
        hit_rate_keys = list(hit_rates.keys())
        selected_hit_key = st.selectbox('选择记录查看详情', hit_rate_keys, index=0, 
                                        format_func=lambda x: f"{hit_rates[x]['prediction_period']}期预测 → {hit_rates[x]['result_period']}期开奖")
        
        data = hit_rates[selected_hit_key]
        
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.markdown(f'''
            <div style="background-color: #e3f2fd; padding: 16px; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #1565c0;">预测期号</h4>
                <p style="font-size: 24px; font-weight: bold;">{data['prediction_period']}</p>
                <p style="margin-bottom: 0;">核心池：{data['core_pool']}</p>
            </div>
            ''', unsafe_allow_html=True)
        
        with col_info2:
            st.markdown(f'''
            <div style="background-color: #fff3e0; padding: 16px; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #ef6c00;">开奖期号</h4>
                <p style="font-size: 24px; font-weight: bold;">{data['result_period']}</p>
                <p style="margin-bottom: 0;">开奖号码：{data['winning_numbers']}</p>
            </div>
            ''', unsafe_allow_html=True)
        
        st.divider()
        st.subheader('🎯 命中统计')
        
        col_stat1, col_stat2 = st.columns(2)
        with col_stat1:
            st.markdown(f'''
            <div style="background-color: #ffebee; padding: 16px; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #c62828;">核心池命中</h4>
                <p style="font-size: 28px; font-weight: bold; color: #c62828;">{data['core_hit_count']}/{data['core_total']}</p>
                <p style="margin-bottom: 0;">命中率：{data['core_hit_rate']:.1f}%</p>
            </div>
            ''', unsafe_allow_html=True)
        
        with col_stat2:
            eight_best = max(data['combinations']['eight_code'], key=lambda x: x['hit_count'])
            six_best = max(data['combinations']['six_code'], key=lambda x: x['hit_count'])
            three_best = max(data['combinations']['three_code'], key=lambda x: x['hit_count'])
            st.markdown(f'''
            <div style="background-color: #f5f5f5; padding: 16px; border-radius: 8px;">
                <h4 style="margin-top: 0; color: #333;">组合最佳命中</h4>
                <p>8码最佳：{eight_best['hit_count']}个</p>
                <p>6码最佳：{six_best['hit_count']}个</p>
                <p>3码最佳：{three_best['hit_count']}个</p>
            </div>
            ''', unsafe_allow_html=True)
        
        # 删除功能
        st.divider()
        st.subheader('🗑️ 删除记录')
        confirm_delete = st.checkbox(f'确认删除 {data["prediction_period"]}期预测 → {data["result_period"]}期开奖 的记录')
        if st.button('🗑️ 删除此记录', type='secondary'):
            if confirm_delete:
                # 构建文件路径并删除
                filepath = os.path.join('hit_rates', f'{selected_hit_key}_hitrate.json')
                if os.path.exists(filepath):
                    os.remove(filepath)
                    st.success(f'✅ 记录已成功删除！')
                    st.rerun()
                else:
                    st.error('❌ 文件不存在')
            else:
                st.error('❌ 请先勾选确认框')
        
        st.divider()
        st.subheader('📋 组合命中详情')
        
        tab_8, tab_6, tab_3 = st.tabs(['10组8码命中详情', '10组6码命中详情', '10组3码命中详情'])
        
        with tab_8:
            col_8_1, col_8_2 = st.columns(2)
            for i, combo in enumerate(data['combinations']['eight_code'], 1):
                display_nums = []
                for num in combo['numbers']:
                    if num in combo['hit_numbers']:
                        display_nums.append(f'<span style="color: #c62828; font-weight: bold;">{num}</span>')
                    else:
                        display_nums.append(str(num))
                result = ' '.join(display_nums)
                bg_color = '#ffebee' if combo['hit_count'] >= 4 else '#f5f5f5'
                if i <= 5:
                    with col_8_1:
                        st.markdown('''<div style="background-color: {}; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">8-{:02d}</span>（命中{}个）：{}</div>'''.format(bg_color, i, combo['hit_count'], result), unsafe_allow_html=True)
                else:
                    with col_8_2:
                        st.markdown('''<div style="background-color: {}; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">8-{:02d}</span>（命中{}个）：{}</div>'''.format(bg_color, i, combo['hit_count'], result), unsafe_allow_html=True)
        
        with tab_6:
            col_6_1, col_6_2 = st.columns(2)
            for i, combo in enumerate(data['combinations']['six_code'], 1):
                display_nums = []
                for num in combo['numbers']:
                    if num in combo['hit_numbers']:
                        display_nums.append(f'<span style="color: #c62828; font-weight: bold;">{num}</span>')
                    else:
                        display_nums.append(str(num))
                result = ' '.join(display_nums)
                bg_color = '#ffebee' if combo['hit_count'] >= 3 else '#f5f5f5'
                if i <= 5:
                    with col_6_1:
                        st.markdown('''<div style="background-color: {}; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">6-{:02d}</span>（命中{}个）：{}</div>'''.format(bg_color, i, combo['hit_count'], result), unsafe_allow_html=True)
                else:
                    with col_6_2:
                        st.markdown('''<div style="background-color: {}; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">6-{:02d}</span>（命中{}个）：{}</div>'''.format(bg_color, i, combo['hit_count'], result), unsafe_allow_html=True)
        
        with tab_3:
            col_3_1, col_3_2 = st.columns(2)
            for i, combo in enumerate(data['combinations']['three_code'], 1):
                display_nums = []
                for num in combo['numbers']:
                    if num in combo['hit_numbers']:
                        display_nums.append(f'<span style="color: #c62828; font-weight: bold;">{num}</span>')
                    else:
                        display_nums.append(str(num))
                result = ' '.join(display_nums)
                bg_color = '#ffebee' if combo['hit_count'] >= 2 else '#f5f5f5'
                if i <= 5:
                    with col_3_1:
                        st.markdown('''<div style="background-color: {}; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">3-{:02d}</span>（命中{}个）：{}</div>'''.format(bg_color, i, combo['hit_count'], result), unsafe_allow_html=True)
                else:
                    with col_3_2:
                        st.markdown('''<div style="background-color: {}; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">3-{:02d}</span>（命中{}个）：{}</div>'''.format(bg_color, i, combo['hit_count'], result), unsafe_allow_html=True)
    else:
        st.info('ℹ️ 暂无命中率记录，请先在 Tab 5 中进行对比并保存')

# ==================== 【Tab 7】体系全流程 SOP（完整实现） ====================
with tabs[6]:
    st.header('📋 体系全流程标准化执行 SOP')
    st.divider()

    # ==================== 【SOP 核心算法模块】 ====================
    def calculate_number_stats(data, period):
        """计算号码的基础统计数据"""
        recent_data = data.tail(period)
        all_numbers = []
        for col in recent_data.columns:
            all_numbers.extend(recent_data[col].dropna().astype(int).tolist())
        
        number_counts = pd.Series(all_numbers).value_counts().reindex(range(1, 81), fill_value=0)
        return number_counts

    def calculate_omission(data, num):
        """计算号码的遗漏期数"""
        last_appear = -1
        for i, (period, row) in enumerate(data.iloc[::-1].iterrows()):
            if num in row.values:
                last_appear = i
                break
        return last_appear if last_appear != -1 else len(data)

    def calculate_cooccurrence(data, num1, num2, period=50):
        """计算两码共现次数"""
        recent_data = data.tail(period)
        count = 0
        for _, row in recent_data.iterrows():
            nums = set(row.dropna().astype(int).tolist())
            if num1 in nums and num2 in nums:
                count += 1
        return count

    def step1_prepare_data(data):
        """Step 1: 基础数据准备"""
        stats_100 = calculate_number_stats(data, 100)
        stats_50 = calculate_number_stats(data, 50)
        stats_30 = calculate_number_stats(data, 30)
        stats_20 = calculate_number_stats(data, 20)
        stats_10 = calculate_number_stats(data, 10)
        
        omission = {}
        for num in range(1, 81):
            omission[num] = calculate_omission(data, num)
        
        return {
            'stats_100': stats_100,
            'stats_50': stats_50,
            'stats_30': stats_30,
            'stats_20': stats_20,
            'stats_10': stats_10,
            'omission': omission
        }

    def step2_risk_control(data, prepared_data):
        """Step 2: 刚性风控规则执行"""
        last_period = data.index[-1]
        last_2_period = data.index[-2] if len(data) >= 2 else None
        last_3_period = data.index[-3] if len(data) >= 3 else None
        
        last_nums = set(data.loc[last_period].dropna().astype(int).tolist())
        last_2_nums = set(data.loc[last_2_period].dropna().astype(int).tolist()) if last_2_period else set()
        last_3_nums = set(data.loc[last_3_period].dropna().astype(int).tolist()) if last_3_period else set()
        
        # 三期连开号
        three_consecutive = last_nums & last_2_nums & last_3_nums
        
        # 两期连开号
        two_consecutive = last_nums & last_2_nums
        
        # 过热熔断号（近10期开出≥5次）
        hot_fuse = []
        stats_10 = prepared_data['stats_10']
        for num in range(1, 81):
            if stats_10[num] >= 5:
                hot_fuse.append(num)
        
        # 最终排除列表
        exclude_list = list(three_consecutive) + list(hot_fuse)
        exclude_list = list(set(exclude_list))
        
        # 降权列表
        downgrade_list = list(two_consecutive - set(exclude_list))
        
        return {
            'three_consecutive': list(three_consecutive),
            'two_consecutive': list(two_consecutive),
            'hot_fuse': hot_fuse,
            'exclude_list': exclude_list,
            'downgrade_list': downgrade_list
        }

    def step3_market_judge(data, prepared_data):
        """Step 3: 行情周期判定"""
        # 近7期数据
        recent_7 = data.tail(7)
        
        # 简单判定：基于号码热度分布
        stats_50 = prepared_data['stats_50']
        hot_thresh = stats_50.quantile(0.8)
        cold_thresh = stats_50.quantile(0.2)
        
        # 统计近7期的热号、温号、冷号占比
        warm_count = 0
        hot_count = 0
        cold_count = 0
        
        for _, row in recent_7.iterrows():
            nums = row.dropna().astype(int).tolist()
            for num in nums:
                if stats_50[num] >= hot_thresh:
                    hot_count += 1
                elif stats_50[num] <= cold_thresh:
                    cold_count += 1
                else:
                    warm_count += 1
        
        total = hot_count + warm_count + cold_count
        warm_ratio = warm_count / total if total > 0 else 0
        hot_ratio = hot_count / total if total > 0 else 0
        
        # 行情判定
        if warm_ratio >= 0.45:
            market_type = "温号主导行情"
        elif hot_ratio >= 0.35:
            market_type = "热号主导行情"
        else:
            market_type = "均衡行情"
        
        # 动态仓位
        if market_type == "温号主导行情":
            position = {'stable': 0.25, 'warm': 0.50, 'hot': 0.10, 'cold': 0.15}
        elif market_type == "热号主导行情":
            position = {'stable': 0.35, 'warm': 0.30, 'hot': 0.20, 'cold': 0.15}
        else:
            position = {'stable': 0.30, 'warm': 0.40, 'hot': 0.15, 'cold': 0.15}
        
        return {
            'market_type': market_type,
            'warm_ratio': warm_ratio,
            'hot_ratio': hot_ratio,
            'position': position
        }

    def step4_select_numbers(data, prepared_data, risk_data, market_data):
        """Step 4: 三大流派号码筛选"""
        stats_100 = prepared_data['stats_100']
        stats_50 = prepared_data['stats_50']
        stats_30 = prepared_data['stats_30']
        stats_20 = prepared_data['stats_20']
        stats_10 = prepared_data['stats_10']
        omission = prepared_data['omission']
        exclude_list = risk_data['exclude_list']
        
        # 第一流派：均衡稳胆流
        stable_candidates = []
        for num in range(1, 81):
            if num in exclude_list:
                continue
            # 100期长期稳定
            if (stats_100[num] >= 20 and 
                stats_30[num] >= 6 and 
                stats_10[num] >= 3 and
                omission[num] <= 4):
                stable_candidates.append(num)
        
        # 按综合评分排序
        stable_scores = {}
        for num in stable_candidates:
            stable_scores[num] = stats_100[num] * 0.4 + stats_50[num] * 0.3 + stats_30[num] * 0.3
        stable_candidates = sorted(stable_candidates, key=lambda x: stable_scores[x], reverse=True)[:7]
        
        # 第二流派：温号轮动流
        warm_candidates = []
        for num in range(1, 81):
            if num in exclude_list or num in stable_candidates:
                continue
            # 遗漏3-6期，近30期出号≥6次
            if (3 <= omission[num] <= 6 and 
                stats_30[num] >= 6 and
                2 <= stats_10[num] <= 3):
                warm_candidates.append(num)
        
        # 按与稳胆的共现率排序
        warm_scores = {}
        for num in warm_candidates:
            score = stats_30[num]
            # 计算与稳胆的共现率
            for stable_num in stable_candidates[:3]:
                score += calculate_cooccurrence(data, num, stable_num, 30) * 2
            warm_scores[num] = score
        warm_candidates = sorted(warm_candidates, key=lambda x: warm_scores[x], reverse=True)[:9]
        
        # 第三流派：热号主攻流
        hot_candidates = []
        for num in range(1, 81):
            if num in exclude_list or num in stable_candidates or num in warm_candidates:
                continue
            # 启动期末-鼎盛期初
            if (stats_50[num] >= 12 and
                3 <= stats_10[num] <= 4 and
                omission[num] <= 3):
                hot_candidates.append(num)
        
        hot_candidates = sorted(hot_candidates, key=lambda x: stats_50[x], reverse=True)[:3]
        
        # 辅助模块：冷号回补流
        cold_candidates = []
        for num in range(1, 81):
            if num in exclude_list or num in stable_candidates or num in warm_candidates or num in hot_candidates:
                continue
            # 黄金回补窗口7-12期
            if (7 <= omission[num] <= 12 and
                stats_100[num] >= 15):
                cold_candidates.append(num)
        
        cold_candidates = sorted(cold_candidates, key=lambda x: omission[x])[:3]
        
        return {
            'stable': stable_candidates,
            'warm': warm_candidates,
            'hot': hot_candidates,
            'cold': cold_candidates
        }

    def step5_build_core_pool(selected_numbers, market_data, risk_data):
        """Step 5: 15码核心池锁定"""
        position = market_data['position']
        total_size = 15
        
        # 按仓位分配
        stable_count = max(1, int(total_size * position['stable']))
        warm_count = max(1, int(total_size * position['warm']))
        hot_count = max(1, int(total_size * position['hot']))
        cold_count = total_size - stable_count - warm_count - hot_count
        
        # 确保冷号数量至少为1
        if cold_count < 1:
            cold_count = 1
            hot_count = max(1, hot_count - 1)
        
        core_pool = []
        
        # 添加各类号码，确保有足够的号码可用
        stable_nums = selected_numbers['stable'][:stable_count] if selected_numbers['stable'] else []
        warm_nums = selected_numbers['warm'][:warm_count] if selected_numbers['warm'] else []
        hot_nums = selected_numbers['hot'][:hot_count] if selected_numbers['hot'] else []
        cold_nums = selected_numbers['cold'][:cold_count] if selected_numbers['cold'] else []
        
        core_pool.extend(stable_nums)
        core_pool.extend(warm_nums)
        core_pool.extend(hot_nums)
        core_pool.extend(cold_nums)
        
        # 去重并排序
        core_pool = sorted(list(set(core_pool)))
        
        # 如果不足15个，从备选池中补充
        if len(core_pool) < total_size:
            all_available = selected_numbers['stable'] + selected_numbers['warm'] + selected_numbers['hot'] + selected_numbers['cold']
            all_available = sorted(list(set(all_available)))
            for num in all_available:
                if num not in core_pool and len(core_pool) < total_size:
                    core_pool.append(num)
        
        # 容错池
        backup_pool = {
            'level1': [num for num in selected_numbers['stable'] + selected_numbers['warm'] if num not in core_pool][:6],
            'level2': [num for num in selected_numbers['hot'] + selected_numbers['cold'] if num not in core_pool][:6],
            'level3': risk_data['three_consecutive'] + risk_data['downgrade_list']
        }
        
        return {
            'core_pool': core_pool,
            'backup_pool': backup_pool
        }

    def step6_build_combinations(core_pool, selected_numbers, data):
        """Step 6: 三层对冲组合构建"""
        
        core_pool_sorted = sorted(core_pool)
        n = len(core_pool_sorted)
        
        eight_code = []
        # 策略1：全核心池覆盖
        for i in range(10):
            if n >= 8:
                # 不同的起始位置和步长
                start = i % n
                step = ((i // 2) % 3) + 1
                comb = []
                for j in range(8):
                    idx = (start + j * step) % n
                    comb.append(core_pool_sorted[idx])
                comb = sorted(list(set(comb)))
                # 如果不够8个，补充
                while len(comb) < 8:
                    for num in core_pool_sorted:
                        if num not in comb:
                            comb.append(num)
                            break
                    comb.sort()
            else:
                # 核心池小于8，重复使用
                comb = (core_pool_sorted * 2)[:8]
            eight_code.append(sorted(comb))
        
        six_code = []
        for i in range(10):
            if n >= 6:
                # 不同策略
                if i == 0:
                    comb = core_pool_sorted[:6]
                elif i == 1:
                    comb = core_pool_sorted[-6:]
                elif i == 2:
                    comb = [core_pool_sorted[i % n] for i in [0, 2, 4, 6, 8, 10]][:6]
                elif i == 3:
                    comb = [core_pool_sorted[i % n] for i in [1, 3, 5, 7, 9, 11]][:6]
                elif i == 4:
                    comb = [core_pool_sorted[i % n] for i in [0, 1, n-2, n-1, n//2-1, n//2]][:6]
                elif i == 5:
                    comb = [core_pool_sorted[i % n] for i in [0, n//3, 2*n//3, n-1, 1, n-2]][:6]
                elif i == 6:
                    comb = [core_pool_sorted[i % n] for i in [0, n-1, 1, n-2, 2, n-3]][:6]
                elif i == 7:
                    comb = [core_pool_sorted[i % n] for i in range(0, n, 2)][:6]
                elif i == 8:
                    comb = [core_pool_sorted[i % n] for i in range(1, n, 2)][:6]
                else:
                    mid = n // 2
                    comb = core_pool_sorted[max(0, mid-3):min(n, mid+3)]
                comb = sorted(list(set(comb)))
                while len(comb) < 6:
                    for num in core_pool_sorted:
                        if num not in comb:
                            comb.append(num)
                            break
                    comb.sort()
            else:
                comb = (core_pool_sorted * 2)[:6]
            six_code.append(sorted(comb))
        
        three_code = []
        # 使用组合策略生成不同的3码组合
        for i in range(10):
            if n >= 3:
                # 不同的组合策略
                if i == 0:
                    comb = core_pool_sorted[:3]
                elif i == 1:
                    comb = core_pool_sorted[-3:]
                elif i == 2:
                    comb = [core_pool_sorted[0], core_pool_sorted[n//2], core_pool_sorted[-1]]
                elif i == 3:
                    comb = [core_pool_sorted[1], core_pool_sorted[n//2], core_pool_sorted[-2]]
                elif i == 4:
                    comb = [core_pool_sorted[0], core_pool_sorted[1], core_pool_sorted[2]]
                elif i == 5:
                    comb = [core_pool_sorted[-3], core_pool_sorted[-2], core_pool_sorted[-1]]
                elif i == 6:
                    comb = [core_pool_sorted[0], core_pool_sorted[n//3], core_pool_sorted[2*n//3]]
                elif i == 7:
                    comb = [core_pool_sorted[1], core_pool_sorted[n//3+1], core_pool_sorted[2*n//3+1]]
                elif i == 8:
                    comb = [core_pool_sorted[0], core_pool_sorted[n-2], core_pool_sorted[n-1]]
                elif i == 9:
                    comb = [core_pool_sorted[n//4], core_pool_sorted[n//2], core_pool_sorted[3*n//4]]
                comb = sorted(list(set(comb)))
                while len(comb) < 3:
                    for num in core_pool_sorted:
                        if num not in comb:
                            comb.append(num)
                            break
                    comb.sort()
            else:
                comb = (core_pool_sorted * 2)[:3]
            three_code.append(sorted(comb))
        
        return {
            'eight_code': eight_code,
            'six_code': six_code,
            'three_code': three_code
        }

    # ==================== 【SOP 主界面】 ====================
    st.markdown("""
    ## 📋 体系全流程标准化执行 SOP
    <div style="background-color: #f0f2f6; padding: 16px; border-radius: 8px; margin-bottom: 20px;">
    <p style="font-size: 16px; line-height: 1.6;">
    本 SOP 为体系的标准化执行流程，每期严格按步骤执行，无主观调整空间，确保每一期预测都可追溯、可复盘。
    </p>
    <ul style="margin-top: 10px; font-size: 14px;">
    <li>✅ 8步标准化流程，确保预测的科学性和一致性</li>
    <li>✅ 基于多周期数据的量化分析</li>
    <li>✅ 自动生成15码核心池和三层对冲组合</li>
    <li>✅ 完整的风控机制，避免极端情况</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)

    # 交互：选择 N 期为 N+1 期预测
    st.divider()
    st.subheader('🔮 为 N+1 期进行预测')
    
    if len(st.session_state.lottery_data) >= 10:
        period_list = st.session_state.lottery_data.index.tolist()
        sop_n_period = st.selectbox(
            '请选择 N 期数（已开奖的最后一期）',
            period_list,
            index=len(period_list)-1,
            help='选择已开奖的最后一期 N，系统将为 N+1 期准备预测'
        )
        
        n_plus_1 = str(int(sop_n_period) + 1)
        st.write(f'已选择 **{sop_n_period}** 期，将为 **{n_plus_1}** 期进行预测')
        
        if st.button('🚀 执行完整 SOP 流程', type='primary', use_container_width=True):
            # 根据选择的期数裁剪数据，只使用到 sop_n_period 期为止的数据
            data = st.session_state.lottery_data.loc[:sop_n_period].copy()
            
            # 进度条和状态显示
            col_progress, col_status = st.columns([1, 3])
            with col_progress:
                progress_bar = st.progress(0)
            with col_status:
                status_text = st.empty()
            
            # Step 1
            status_text.markdown('<div style="color: #1e88e5; font-weight: bold;">Step 1/8: 基础数据准备...</div>', unsafe_allow_html=True)
            prepared_data = step1_prepare_data(data)
            progress_bar.progress(12)
            
            # Step 2
            status_text.markdown('<div style="color: #1e88e5; font-weight: bold;">Step 2/8: 刚性风控规则执行...</div>', unsafe_allow_html=True)
            risk_data = step2_risk_control(data, prepared_data)
            progress_bar.progress(25)
            
            # Step 3
            status_text.markdown('<div style="color: #1e88e5; font-weight: bold;">Step 3/8: 行情周期判定...</div>', unsafe_allow_html=True)
            market_data = step3_market_judge(data, prepared_data)
            progress_bar.progress(37)
            
            # Step 4
            status_text.markdown('<div style="color: #1e88e5; font-weight: bold;">Step 4/8: 三大流派号码筛选...</div>', unsafe_allow_html=True)
            selected_numbers = step4_select_numbers(data, prepared_data, risk_data, market_data)
            progress_bar.progress(50)
            
            # Step 5
            status_text.markdown('<div style="color: #1e88e5; font-weight: bold;">Step 5/8: 15码核心池锁定...</div>', unsafe_allow_html=True)
            core_pool_data = step5_build_core_pool(selected_numbers, market_data, risk_data)
            progress_bar.progress(62)
            
            # Step 6
            status_text.markdown('<div style="color: #1e88e5; font-weight: bold;">Step 6/8: 三层对冲组合构建...</div>', unsafe_allow_html=True)
            combinations = step6_build_combinations(core_pool_data['core_pool'], selected_numbers, data)
            progress_bar.progress(75)
            
            # Step 7
            status_text.markdown('<div style="color: #1e88e5; font-weight: bold;">Step 7/8: 终版方案存档锁定...</div>', unsafe_allow_html=True)
            prediction_data = {
                'period': n_plus_1,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'step1_prepared': {
                    'stats_100': prepared_data['stats_100'].to_dict(),
                    'omission': prepared_data['omission']
                },
                'step2_risk': risk_data,
                'step3_market': market_data,
                'step4_selected': selected_numbers,
                'step5_core_pool': core_pool_data,
                'step6_combinations': combinations,
                'core_pool': ' '.join(map(str, sorted(core_pool_data['core_pool']))),
                'combinations': combinations
            }
            filename = save_prediction(prediction_data, n_plus_1)
            st.session_state['prediction_data'] = prediction_data
            progress_bar.progress(87)
            
            # Step 8
            status_text.text('Step 8/8: 完成！')
            progress_bar.progress(100)
            
            # 展示结果
            st.success(f'✅ SOP 流程执行完成！预测方案已保存至：{filename}')
            st.divider()
            
            # 展示 Step 2 风控结果
            st.subheader('📌 Step 2: 刚性风控执行结果')
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                st.markdown('''
                <div style="background-color: #ffebee; padding: 12px; border-radius: 6px;">
                <h4 style="margin-top: 0; color: #c62828;">三期连开号（剔除）</h4>
                <p>{}</p>
                </div>
                '''.format(risk_data['three_consecutive'] if risk_data['three_consecutive'] else '无'), unsafe_allow_html=True)
            with col_r2:
                st.markdown('''
                <div style="background-color: #fff3e0; padding: 12px; border-radius: 6px;">
                <h4 style="margin-top: 0; color: #ef6c00;">两期连开号（降权）</h4>
                <p>{}</p>
                </div>
                '''.format(risk_data['downgrade_list'] if risk_data['downgrade_list'] else '无'), unsafe_allow_html=True)
            with col_r3:
                st.markdown('''
                <div style="background-color: #e3f2fd; padding: 12px; border-radius: 6px;">
                <h4 style="margin-top: 0; color: #1565c0;">过热熔断号（剔除）</h4>
                <p>{}</p>
                </div>
                '''.format(risk_data['hot_fuse'] if risk_data['hot_fuse'] else '无'), unsafe_allow_html=True)
            
            # 展示 Step 3 行情判定
            st.divider()
            st.subheader('📌 Step 3: 行情周期判定')
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.markdown('''
                <div style="background-color: #e8f5e8; padding: 16px; border-radius: 8px; text-align: center;">
                <h3 style="margin-top: 0; color: #2e7d32;">{}</h3>
                <p style="margin-bottom: 0; color: #2e7d32;">判定行情类型</p>
                </div>
                '''.format(market_data['market_type']), unsafe_allow_html=True)
            with col_m2:
                st.markdown('''
                <div style="background-color: #f3e5f5; padding: 12px; border-radius: 6px;">
                <h4 style="margin-top: 0; color: #7b1fa2;">动态仓位分配</h4>
                <ul style="margin-bottom: 0;">
                <li>均衡稳胆流：{}%</li>
                <li>温号轮动流：{}%</li>
                <li>热号主攻流：{}%</li>
                <li>冷号回补流：{}%</li>
                </ul>
                </div>
                '''.format(
                    int(market_data["position"]["stable"]*100),
                    int(market_data["position"]["warm"]*100),
                    int(market_data["position"]["hot"]*100),
                    int(market_data["position"]["cold"]*100)
                ), unsafe_allow_html=True)
            
            # 展示 Step 4-5 核心池
            st.divider()
            st.subheader('📌 Step 4-5: 15码终版核心池')
            col_c1, col_c2 = st.columns([3, 1])
            with col_c1:
                st.markdown('''<div style="background-color: #e3f2fd; padding: 16px; border-radius: 8px; margin-bottom: 12px;"><h4 style="margin-top: 0; color: #1565c0;">15码核心池（升序）</h4><p style="font-family: monospace; font-size: 14px;">{}</p></div>'''.format(' '.join(map(str, sorted(core_pool_data['core_pool'])))), unsafe_allow_html=True)
                
                col_flow1, col_flow2 = st.columns(2)
                with col_flow1:
                    st.markdown('''<div style="background-color: #e8f5e8; padding: 12px; border-radius: 6px;"><h4 style="margin-top: 0; color: #2e7d32;">S级稳胆</h4><p>{}</p></div>'''.format(selected_numbers['stable']), unsafe_allow_html=True)
                    st.markdown('''<div style="background-color: #fff3e0; padding: 12px; border-radius: 6px; margin-top: 12px;"><h4 style="margin-top: 0; color: #ef6c00;">B级热号</h4><p>{}</p></div>'''.format(selected_numbers['hot']), unsafe_allow_html=True)
                with col_flow2:
                    st.markdown('''<div style="background-color: #fffde7; padding: 12px; border-radius: 6px;"><h4 style="margin-top: 0; color: #f57f17;">A级温号</h4><p>{}</p></div>'''.format(selected_numbers['warm']), unsafe_allow_html=True)
                    st.markdown('''<div style="background-color: #f3e5f5; padding: 12px; border-radius: 6px; margin-top: 12px;"><h4 style="margin-top: 0; color: #7b1fa2;">C级冷号</h4><p>{}</p></div>'''.format(selected_numbers['cold']), unsafe_allow_html=True)
            with col_c2:
                st.markdown('''<div style="background-color: #fce4ec; padding: 12px; border-radius: 6px; margin-bottom: 12px;"><h4 style="margin-top: 0; color: #c2185b;">一级备选池</h4><p>{}</p></div>'''.format(core_pool_data['backup_pool']['level1']), unsafe_allow_html=True)
                st.markdown('''<div style="background-color: #e0f7fa; padding: 12px; border-radius: 6px; margin-bottom: 12px;"><h4 style="margin-top: 0; color: #006064;">二级对冲池</h4><p>{}</p></div>'''.format(core_pool_data['backup_pool']['level2']), unsafe_allow_html=True)
                st.markdown('''<div style="background-color: #ffebee; padding: 12px; border-radius: 6px;"><h4 style="margin-top: 0; color: #c62828;">三级极端容错池</h4><p>{}</p></div>'''.format(core_pool_data['backup_pool']['level3']), unsafe_allow_html=True)
            
            # 展示 Step 6 组合
            st.divider()
            st.subheader('📌 Step 6: 全玩法组合打法')
            
            tab_8, tab_6, tab_3 = st.tabs(['10组8码', '10组6码', '10组3码'])
            with tab_8:
                col_8_1, col_8_2 = st.columns(2)
                for i, comb in enumerate(combinations['eight_code'], 1):
                    if i <= 5:
                        with col_8_1:
                            st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">8-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, sorted(comb)))), unsafe_allow_html=True)
                    else:
                        with col_8_2:
                            st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">8-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, sorted(comb)))), unsafe_allow_html=True)
            with tab_6:
                col_6_1, col_6_2 = st.columns(2)
                for i, comb in enumerate(combinations['six_code'], 1):
                    if i <= 5:
                        with col_6_1:
                            st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">6-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, sorted(comb)))), unsafe_allow_html=True)
                    else:
                        with col_6_2:
                            st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">6-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, sorted(comb)))), unsafe_allow_html=True)
            with tab_3:
                col_3_1, col_3_2 = st.columns(2)
                for i, comb in enumerate(combinations['three_code'], 1):
                    if i <= 5:
                        with col_3_1:
                            st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">3-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, sorted(comb)))), unsafe_allow_html=True)
                    else:
                        with col_3_2:
                            st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">3-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, sorted(comb)))), unsafe_allow_html=True)
    
    if len(st.session_state.lottery_data) >= 10 and 'auto_run_sop' in st.session_state and st.session_state['auto_run_sop']:
        last_period = st.session_state.lottery_data.index[-1]
        n_plus_1 = str(int(last_period) + 1)

        with st.spinner(f'🔄 检测到新增数据，正在自动为 {n_plus_1} 期生成预测...'):
            data = st.session_state.lottery_data.loc[:last_period].copy()

            prepared_data = step1_prepare_data(data)
            risk_data = step2_risk_control(data, prepared_data)
            market_data = step3_market_judge(data, prepared_data)
            selected_numbers = step4_select_numbers(data, prepared_data, risk_data, market_data)
            core_pool_data = step5_build_core_pool(selected_numbers, market_data, risk_data)
            combinations = step6_build_combinations(core_pool_data['core_pool'], selected_numbers, data)

            prediction_data = {
                'period': n_plus_1,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'auto_generated': True,
                'step1_prepared': {
                    'stats_100': prepared_data['stats_100'].to_dict(),
                    'omission': prepared_data['omission']
                },
                'step2_risk': risk_data,
                'step3_market': market_data,
                'step4_selected': selected_numbers,
                'step5_core_pool': core_pool_data,
                'step6_combinations': combinations,
                'core_pool': ' '.join(map(str, sorted(core_pool_data['core_pool']))),
                'combinations': combinations
            }

            save_prediction(prediction_data, n_plus_1)
            st.session_state['prediction_data'] = prediction_data
            st.session_state['auto_run_sop'] = False

        st.success(f'✅ 自动预测完成！已为 **{n_plus_1}** 期生成预测方案')

        st.divider()
        st.subheader('📌 Step 2: 刚性风控执行结果')
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            st.markdown('''
            <div style="background-color: #ffebee; padding: 12px; border-radius: 6px;">
            <h4 style="margin-top: 0; color: #c62828;">三期连开号（剔除）</h4>
            <p>{}</p>
            </div>
            '''.format(risk_data['three_consecutive'] if risk_data['three_consecutive'] else '无'), unsafe_allow_html=True)
        with col_r2:
            st.markdown('''
            <div style="background-color: #fff3e0; padding: 12px; border-radius: 6px;">
            <h4 style="margin-top: 0; color: #ef6c00;">两期连开号（降权）</h4>
            <p>{}</p>
            </div>
            '''.format(risk_data['downgrade_list'] if risk_data['downgrade_list'] else '无'), unsafe_allow_html=True)
        with col_r3:
            st.markdown('''
            <div style="background-color: #e3f2fd; padding: 12px; border-radius: 6px;">
            <h4 style="margin-top: 0; color: #1565c0;">过热熔断号（剔除）</h4>
            <p>{}</p>
            </div>
            '''.format(risk_data['hot_fuse'] if risk_data['hot_fuse'] else '无'), unsafe_allow_html=True)

        st.divider()
        st.subheader('📌 Step 3: 行情周期判定')
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.markdown('''
            <div style="background-color: #e8f5e8; padding: 16px; border-radius: 8px; text-align: center;">
            <h3 style="margin-top: 0; color: #2e7d32;">{}</h3>
            <p style="margin-bottom: 0; color: #2e7d32;">判定行情类型</p>
            </div>
            '''.format(market_data['market_type']), unsafe_allow_html=True)
        with col_m2:
            st.markdown('''
            <div style="background-color: #f3e5f5; padding: 12px; border-radius: 6px;">
            <h4 style="margin-top: 0; color: #7b1fa2;">动态仓位分配</h4>
            <ul style="margin-bottom: 0;">
            <li>均衡稳胆流：{}%</li>
            <li>温号轮动流：{}%</li>
            <li>热号主攻流：{}%</li>
            <li>冷号回补流：{}%</li>
            </ul>
            </div>
            '''.format(
                int(market_data["position"]["stable"]*100),
                int(market_data["position"]["warm"]*100),
                int(market_data["position"]["hot"]*100),
                int(market_data["position"]["cold"]*100)
            ), unsafe_allow_html=True)

        st.divider()
        st.subheader('📌 Step 4-5: 15码终版核心池')
        col_c1, col_c2 = st.columns([3, 1])
        with col_c1:
            st.markdown('''<div style="background-color: #e3f2fd; padding: 16px; border-radius: 8px; margin-bottom: 12px;"><h4 style="margin-top: 0; color: #1565c0;">15码核心池（升序）</h4><p style="font-family: monospace; font-size: 14px;">{}</p></div>'''.format(' '.join(map(str, sorted(core_pool_data['core_pool'])))), unsafe_allow_html=True)

            col_flow1, col_flow2 = st.columns(2)
            with col_flow1:
                st.markdown('''<div style="background-color: #e8f5e8; padding: 12px; border-radius: 6px;"><h4 style="margin-top: 0; color: #2e7d32;">S级稳胆</h4><p>{}</p></div>'''.format(selected_numbers['stable']), unsafe_allow_html=True)
                st.markdown('''<div style="background-color: #fff3e0; padding: 12px; border-radius: 6px; margin-top: 12px;"><h4 style="margin-top: 0; color: #ef6c00;">B级热号</h4><p>{}</p></div>'''.format(selected_numbers['hot']), unsafe_allow_html=True)
            with col_flow2:
                st.markdown('''<div style="background-color: #fffde7; padding: 12px; border-radius: 6px;"><h4 style="margin-top: 0; color: #f57f17;">A级温号</h4><p>{}</p></div>'''.format(selected_numbers['warm']), unsafe_allow_html=True)
                st.markdown('''<div style="background-color: #f3e5f5; padding: 12px; border-radius: 6px; margin-top: 12px;"><h4 style="margin-top: 0; color: #7b1fa2;">C级冷号</h4><p>{}</p></div>'''.format(selected_numbers['cold']), unsafe_allow_html=True)
        with col_c2:
            st.markdown('''<div style="background-color: #fce4ec; padding: 12px; border-radius: 6px; margin-bottom: 12px;"><h4 style="margin-top: 0; color: #c2185b;">一级备选池</h4><p>{}</p></div>'''.format(core_pool_data['backup_pool']['level1']), unsafe_allow_html=True)
            st.markdown('''<div style="background-color: #e0f7fa; padding: 12px; border-radius: 6px; margin-bottom: 12px;"><h4 style="margin-top: 0; color: #006064;">二级对冲池</h4><p>{}</p></div>'''.format(core_pool_data['backup_pool']['level2']), unsafe_allow_html=True)
            st.markdown('''<div style="background-color: #ffebee; padding: 12px; border-radius: 6px;"><h4 style="margin-top: 0; color: #c62828;">三级极端容错池</h4><p>{}</p></div>'''.format(core_pool_data['backup_pool']['level3']), unsafe_allow_html=True)

        st.divider()
        st.subheader('📌 Step 6: 全玩法组合打法（自动生成）')

        tab_8, tab_6, tab_3 = st.tabs(['10组8码', '10组6码', '10组3码'])
        with tab_8:
            col_8_1, col_8_2 = st.columns(2)
            for i, comb in enumerate(combinations['eight_code'], 1):
                if i <= 5:
                    with col_8_1:
                        st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">8-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, sorted(comb)))), unsafe_allow_html=True)
                else:
                    with col_8_2:
                        st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">8-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, sorted(comb)))), unsafe_allow_html=True)
        with tab_6:
            col_6_1, col_6_2 = st.columns(2)
            for i, comb in enumerate(combinations['six_code'], 1):
                if i <= 5:
                    with col_6_1:
                        st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">6-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, sorted(comb)))), unsafe_allow_html=True)
                else:
                    with col_6_2:
                        st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">6-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, sorted(comb)))), unsafe_allow_html=True)
        with tab_3:
            col_3_1, col_3_2 = st.columns(2)
            for i, comb in enumerate(combinations['three_code'], 1):
                if i <= 5:
                    with col_3_1:
                        st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">3-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, sorted(comb)))), unsafe_allow_html=True)
                else:
                    with col_3_2:
                        st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">3-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, sorted(comb)))), unsafe_allow_html=True)

        st.info(f'📅 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}（自动执行）')
    
    elif len(st.session_state.lottery_data) < 10:
        st.warning('⚠️ 数据不足 10 期，无法执行完整 SOP 流程')

# ==================== 【Tab 8】预测结果存档 ====================
with tabs[7]:
    st.header('🔮 预测结果存档')
    st.divider()
    
    # 加载所有已保存的预测记录
    predictions = load_all_predictions()
    
    if predictions:
        # 选择期号
        period_list = list(predictions.keys())
        selected_period = st.selectbox('选择预测期号', period_list, index=len(period_list)-1)
        
        pred = predictions[selected_period]
        
        # 显示预测信息
        st.markdown(f'''<div style="background-color: #e3f2fd; padding: 16px; border-radius: 8px; margin-bottom: 12px;"><h4 style="margin-top: 0; color: #1565c0;">{selected_period}期预测号码库</h4><p style="font-family: monospace; font-size: 14px;">{pred['core_pool']}</p></div>''', unsafe_allow_html=True)
        
        st.subheader('📌 {}期预测组合打法'.format(selected_period))
        
        tab_8, tab_6, tab_3 = st.tabs(['10组8码', '10组6码', '10组3码'])
        with tab_8:
            eight_code = pred['combinations']['eight_code']
            col_8_1, col_8_2 = st.columns(2)
            for i, comb in enumerate(eight_code, 1):
                if i <= 5:
                    with col_8_1:
                        st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">8-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, comb))), unsafe_allow_html=True)
                else:
                    with col_8_2:
                        st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">8-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, comb))), unsafe_allow_html=True)
        with tab_6:
            six_code = pred['combinations']['six_code']
            col_6_1, col_6_2 = st.columns(2)
            for i, comb in enumerate(six_code, 1):
                if i <= 5:
                    with col_6_1:
                        st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">6-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, comb))), unsafe_allow_html=True)
                else:
                    with col_6_2:
                        st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">6-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, comb))), unsafe_allow_html=True)
        with tab_3:
            three_code = pred['combinations']['three_code']
            col_3_1, col_3_2 = st.columns(2)
            for i, comb in enumerate(three_code, 1):
                if i <= 5:
                    with col_3_1:
                        st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">3-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, comb))), unsafe_allow_html=True)
                else:
                    with col_3_2:
                        st.markdown('''<div style="background-color: #f5f5f5; padding: 8px; border-radius: 4px; margin-bottom: 8px;"><span style="font-weight: bold;">3-{:02d}</span>：{}</div>'''.format(i, ' '.join(map(str, comb))), unsafe_allow_html=True)
        
        # 显示生成时间
        if 'generated_at' in pred:
            st.info(f'📅 生成时间：{pred["generated_at"]}')
    else:
        st.info('暂无预测记录，请先在 Tab 7 中执行 SOP 流程生成预测')

# ==================== 【Tab 9】预留板块 ====================
with tabs[8]:
    st.header('⚙️ 预留板块')
    st.divider()
    st.info('🚧 **板块预留，可用于后续功能扩展：**\n- 自定义参数设置（风控阈值、流派权重等）\n- 批量数据导入（Excel/CSV）\n- 可视化图表增强（遗漏图、走势图等）\n- 移动端适配优化\n- 用户权限管理（多账号）')
