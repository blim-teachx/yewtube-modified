import json
import os, glob
import random
import re
from urllib.parse import parse_qs, urlparse

import requests
import yt_dlp
from youtubesearchpython import VideosSearch, ChannelsSearch, PlaylistsSearch, Suggestions, Playlist, playlist_from_channel_id, Comments, Video, Channel, ChannelSearch
import time

class MyLogger:

    def __init__(self, print_info=False):
        self.print_info = print_info

    def debug(self, msg):
        # For compatibility with youtube-dl, both debug and info are passed into debug
        # You can distinguish them by the prefix '[debug] '
        if msg.startswith('[debug] '):
            pass
        else:
            self.info(msg)

    def info(self, msg):
        if self.print_info:
            print(msg)

    def warning(self, msg):
        pass

    def error(self, msg):
        print(msg)


class PafyStream:
    def __init__(self, format_dict):
        self._format = format_dict
        self.url = format_dict.get('url', '')
        self.extension = format_dict.get('ext', 'mp4')
        vcodec = format_dict.get('vcodec')
        acodec = format_dict.get('acodec')
        height = format_dict.get('height')
        width = format_dict.get('width')
        fps = format_dict.get('fps')
        if vcodec == 'none':
            self.mediatype = 'audio'
            self.resolution = 'audio only'
            abr = format_dict.get('abr', 0)
            self.quality = f"{abr}kbps" if abr else 'unknown'
        else:
            self.mediatype = 'video' if acodec == 'none' else 'na'
            self.resolution = f"{width or 0}x{height or 0}"
            self.quality = format_dict.get('format_note', f"{height or 0}p")
        self.notes = f"{fps}fps" if fps else ''
        self.threed = '3d' in self.notes.lower() or 'stereo' in self.resolution.lower()
        self.acodec = acodec
        self.vcodec = vcodec
        self.bitrate = format_dict.get('abr', format_dict.get('vbr', -1))
        self.filesize = self.get_filesize()

    def get_filesize(self):
        fs = self._format.get('filesize')
        if fs is not None:
            return fs
        fs = self._format.get('filesize_approx')
        return fs or 0


class Pafy:
    def __init__(self, info_dict, ytid):
        self._info = info_dict
        self.title = info_dict.get('title', 'Unknown')
        self.author = info_dict.get('uploader', 'Unknown')
        self.length = info_dict.get('duration', 0)
        self.duration = self.length
        self.videoid = ytid
        self.fresh = True
        formats = info_dict.get('formats', [])
        filtered_formats = [f for f in formats if f.get('format_note') != 'storyboard']
        self.allstreams = [PafyStream(f) for f in filtered_formats]
        self.audiostreams = [s for s in self.allstreams if s.mediatype == 'audio']
        self.videostreams = [s for s in self.allstreams if s.mediatype != 'audio']
        self.expiry = time.time() + 7200


def new(ytid, callback=None):
    logger = MyLogger(print_info=False)
    ydl_opts = {'logger': logger}
    # TODO: implement callback as progress_hook if provided
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(f'https://www.youtube.com/watch?v={ytid}', download=False)
    p = Pafy(info_dict, ytid)
    return p


def get_video_streams(ytid):

    '''
    given a youtube video id returns different video / audio stream formats' \
    '''

    with yt_dlp.YoutubeDL({'logger':MyLogger()}) as ydl:
        info_dict = ydl.extract_info(ytid, download=False)
        return [i for i in info_dict['formats'] if i.get('format_note') != 'storyboard']


def download_video(ytid, folder, audio_only=False):

    '''
    Given a youtube video id and target folder, this function will download video to that folder
    '''

    ytdl_format_options = {
        'outtmpl': os.path.join(folder, '%(title)s-%(id)s.%(ext)s')
    }
    if audio_only:
        ytdl_format_options['format'] = 'bestaudio/best'
        ytdl_format_options['postprocessors'] =[{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    with yt_dlp.YoutubeDL(ytdl_format_options) as ydl:
        ydl.download('https://www.youtube.com/watch?v=%s' % ytid)
        return True

def search_videos(query, pages):

    '''
    Given a keyword / query this function will return youtube video results against those keywords / query
    '''

    videosSearch = VideosSearch(query, limit=50)
    wdata = videosSearch.result()['result']
    for i in range(pages-1):
        videosSearch.next()
        wdata.extend(videosSearch.result()['result'])
    return wdata


def channel_search(query):

    '''
    Search channel based on keyword / query provided by user
    '''

    channelsSearch = ChannelsSearch(query, limit=50, region='US')
    return channelsSearch.result()['result']

def playlist_search(query):

    '''
    Returns all playlists having similar names as keyword / query provided
    '''

    playlistsSearch = PlaylistsSearch(query, limit=50)
    return playlistsSearch.result()['result']

def get_playlist(playlist_id):

    '''
    Get all videos of a playlist identified by playlist_id
    '''

    playlist = Playlist('https://www.youtube.com/playlist?list=%s' % playlist_id)
    while playlist.hasMoreVideos:
        playlist.getNextVideos()
    return playlist

def get_video_title_suggestions(query):
    suggestions = Suggestions(language = 'en', region = 'US')
    related_searches = suggestions.get(query)['result']
    return related_searches[random.randint(0,len(related_searches))]

def channel_id_from_name(query):
    channel_info = channel_search(query)[0]
    channel_id = channel_info['id']
    channel_name = channel_info['title']
    return (channel_id, channel_name)

def all_videos_from_channel(channel_id):
    '''
    Get all videos of a playlist identified by channel_id
    '''

    playlist = Playlist(playlist_from_channel_id(channel_id))
    while playlist.hasMoreVideos:
        playlist.getNextVideos()
    return playlist.videos

def search_videos_from_channel(channel_id, query):
    search = ChannelSearch(query , channel_id)
    return search.result()

def get_comments(video_id):
    comments = Comments.get(video_id)
    return comments['result']

def get_video_info(video_id):
    try:
        videoInfo = Video.getInfo(video_id)
        response = return_dislikes(video_id)
        videoInfo['likes'] = response['likes']
        videoInfo['dislikes'] = response['dislikes']
        videoInfo['averageRating'] = response['rating']
        return videoInfo
    except:
        raise Exception("Can't get video info. Video is either private or unavailable in your country.")

def return_dislikes(video_id):
    return json.loads(requests.get('https://returnyoutubedislikeapi.com/votes?videoId=' + video_id).text)


def extract_video_id(url: str) -> str:
    """Extract the video id from a url, return video id as str.

    Args:
        url: url contain video id

    Returns:
        video id

    Raises:
        ValueError: If no video id found

    Examples:

        >>> extract_video_id('http://example.com')
        >>> extract_video_id('https://www.youtube.com/watch?v=LDU_Txk06tM')
        LDU_Txk06tM
        >>> extract_video_id('https://youtu.be/LDU_Txk06tM')
        LDU_Txk06tM
    """
    idregx = re.compile(r'[\w-]{11}$')
    url = str(url).strip()

    if idregx.match(url):
        return url # ID of video

    if '://' not in url:
        url = '//' + url
    parsedurl = urlparse(url)
    if parsedurl.netloc in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'gaming.youtube.com'):
        query = parse_qs(parsedurl.query)
        if 'v' in query and idregx.match(query['v'][0]):
            return query['v'][0]
    elif parsedurl.netloc in ('youtu.be', 'www.youtu.be'):
        vidid = parsedurl.path.split('/')[-1] if parsedurl.path else ''
        if idregx.match(vidid):
            return vidid

    err = "Need 11 character video id or the URL of the video. Got %s"
    raise ValueError(err % url)

def all_playlists_from_channel(channel_id):
    channel = Channel(channel_id)
    playlists = channel.result['playlists']
    while channel.has_more_playlists():
         channel.next()
         playlists.extend(channel.result["playlists"])
    return playlists

def get_subtitles(ytid, output_dir):
    '''
    Downloads and saves the .vtt subtitle of give youtube video id under path {output_dir}/subtitles
    Subtitles are selected as follows:
    1. Select first user provided subtitle. If none then
    2. Select auto generated 'en' subtitles
    '''

    if output_dir.endswith('/'):
        output_dir = output_dir[:-1]
    outtmpl = f'{output_dir}/subtitles/{ytid}'
    # check if subtitles already exist
    existing_subtitles = glob.glob(os.path.join(outtmpl+'*.vtt'))
    if existing_subtitles:
        return existing_subtitles[0]

    url = f'https://www.youtube.com/watch?v={ytid}'
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitlesformat': 'vtt',
        'outtmpl': outtmpl,
        'logger': MyLogger(print_info=False),
    }
    # Create a YoutubeDL instance with the options
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        subtitles = info_dict.get('subtitles', {})
        available_formats = list(subtitles.keys())
        if available_formats:
            lang = available_formats[0] # pick first subtitle from user-uploaded subtitles
        else:
            lang = 'en' # otherwise use english auto-generated subtitles
        ydl.params['subtitleslangs'] = [lang]
        # Add the new options to the existing ydl_opts dictionary
        ydl.add_default_info_extractors()
        # Create a new yt-dlp object with the updated ydl_opts dictionary
        ydl = yt_dlp.YoutubeDL(ydl_opts)
        # Download the subtitle
        ydl.download([url])
        path = f'{outtmpl}.{lang}.vtt'
        return path if os.path.isfile(path) else None