#!/usr/bin/env python3
"""
Simple Silent URL Cleaner
Removes tracking parameters from clipboard URLs and converts Twitter posts to fxtwitter
Monitors clipboard for any changes (copy via Ctrl+C, right-click, etc.)
Requirements: pip install pyperclip
"""
import keyboard
import pyperclip
import time
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import os
import sys
from datetime import datetime

class SilentURLCleaner:
    def __init__(self):
        # Get executable directory for file paths
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            self.app_dir = os.path.dirname(sys.executable)
        else:
            # Running as script
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Set process title for better visibility in task manager
        try:
            if os.name == 'nt':
                import ctypes
                ctypes.windll.kernel32.SetConsoleTitleW("URL Cleaner Service")
        except:
            pass
        
        self.last_clipboard = ""
        self.is_running = True
        self.log_file = os.path.join(self.app_dir, "url_cleaner_log.txt")
        
        # Tracking parameters to remove
        self.tracking_params = {
            # Facebook/Meta
            'fbclid', 'fb_action_ids', 'fb_action_types', 'fb_ref', 'fb_source',
            'fb_comment_id', 'comment_tracking', 'notif_id', 'notif_t',
            
            # Google Analytics & Ads  
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'utm_id', 'utm_source_platform', 'utm_creative_format', 'utm_marketing_tactic',
            'gclid', 'gclsrc', 'dclid', 'gbraid', 'wbraid', '_ga', '_gl',
            
            # Twitter/X
            't', 's', 'ref_src', 'ref_url', 'twclid', 'twitter-impression-id',
            
            # YouTube
            'feature', 'kw', 'si', 'app', 'persist_app', 'noapp', 'has_verified',
            'list', 'index', 'pp', 'source_ve_path', 'ab_channel', 'autoplay',

            # Others
            'msclkid', 'cvid', 'trk', 'trkInfo', 'li_fat_id', 'lipi',
            'utm_name', 'rdt_cid', 'share_id', 'context',
            'is_copy_url', 'sender_device', 'sender_web_id', 'tt_from',
            'igshid', 'igsh', 'img_index', 'amp_analytics',
            'mc_cid', 'mc_eid', 'yclid', 'ncid', '_hsenc', '_hsmi'
        }
        
        # Supported domains
        self.supported_domains = [
            'facebook.com', 'fb.com', 'm.facebook.com',
            'twitter.com', 'x.com', 'mobile.twitter.com',
            'youtube.com', 'youtu.be', 'm.youtube.com',
            'instagram.com', 'm.instagram.com',
            'linkedin.com', 'm.linkedin.com',
            'reddit.com', 'old.reddit.com',
            'pixiv.com'
        ]
        
        self.domain_to_name = {
            "twitter": ["twitter.com", "x.com", "mobile.twitter.com"],
            "pixiv": "pixiv.net"
        }

        self.raw_cdomain = {}
        for key, values in self.domain_to_name.items():
            for value in values:
                self.raw_cdomain[value] = key 
        

        self.converted_domains = {
            "twitter": "fxtwitter.com",
            "pixiv": "phixiv.net"
        }
        self.convert_condition = {
            "twitter": "status",
            "pixiv": "artworks"
        }

        # Log startup
        self.log("=" * 50)
        self.log("URL Cleaner Service started")
        self.log(f"Log file location: {self.log_file}")
        self.log(f"Executable directory: {self.app_dir}")

        #keyboard.add_hotkey('ctrl+alt+v', copy_hotkey)
    
    def log(self, message):
        """Write message to log file with timestamp"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] {message}\n"
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
            
            # Also print to console
            print(log_entry.strip())
            
        except Exception as e:
            print(f"Logging error: {e}")
    
    def is_url(self, text):
        """Simple URL validation"""
        if not isinstance(text, str) or len(text) > 200 or len(text) < 10:
            return False
        
        text = text.strip()
        
        # Simple check for http/https URLs
        return text.startswith(('http://', 'https://')) and ' ' not in text
    
    def is_supported_platform(self, url):
        """Check if URL is from supported platforms"""
        try:
            domain = urlparse(url).netloc.lower().replace('www.', '')
            return any(platform in domain for platform in self.supported_domains)
        except:
            return False
    
    def clean_url(self, url):
        """Remove tracking parameters from URL"""
        try:
            query_params = parse_qs(url.query)
            cleaned_params = {}
            removed = []
            
            for param, values in query_params.items():
                # Keep YouTube timestamp parameter
                is_youtube_timestamp = (param.lower() == 't' and 
                                      any(domain in parsed.netloc.lower() 
                                          for domain in ['youtube.com', 'youtu.be', 'm.youtube.com']))
                
                if is_youtube_timestamp or param.lower() not in self.tracking_params:
                    cleaned_params[param] = values
                else:
                    removed.append(param)
            
            # Rebuild URL
            new_query = urlencode(cleaned_params, doseq=True)
            cleaned_url = urlunparse((
                parsed.scheme, 
                parsed.netloc, 
                parsed.path,
                parsed.params, 
                new_query, 
                parsed.fragment
            ))
            
            return cleaned_url, removed
            
        except:
            return url, []


    def process_clipboard(self, current):
        """Process clipboard content"""
        try:
            if self.is_url(current) and self.is_supported_platform(current):
                self.log(f"Valid URL detected: {current[:100]}...")
                
                parsed = urlparse(current)

                # Clean tracking parameters
                cleaned, removed = self.clean_url(current)
                #parsed again for domain convertion
                parsed_cleanUrl = urlparse(cleaned)
                was_converted = False

                domain = parsed_cleanUrl.netloc.lower().replace('www.', '')
                domain_name = self.raw_cdomain.get(domain, 0)
                if (domain_name):
                    if (self.convert_condition.get(domain_name) in parsed_cleanUrl.path):
                            was_converted = True
                            final_url = urlunparse((
                                parsed_cleanUrl.scheme, 
                                self.converted_domains.get(domain_name), 
                                parsed_cleanUrl.path, 
                                parsed_cleanUrl.params, 
                                parsed_cleanUrl.query, 
                                parsed_cleanUrl.fragment))

                #Log
                changes = []
                if removed:
                    changes.append(f"removed {len(removed)} tracking params: {', '.join(removed[:5])}")
                if was_converted:
                    changes.append("converted the link")
                if (changes != []):
                    self.log(f"✓ URL cleaned! ({', '.join(changes)})")
                    self.log(f"  Final URL: {final_url}")

                if was_converted:
                    pyperclip.copy(final_url)
                    return True
                elif removed:
                    pyperclip.copy(cleaned)
                    return True
                else:
                    self.log("URL is already clean - no changes needed")
                    return False 
            return False
            
        except Exception as e:
            self.log(f"Error processing clipboard: {str(e)}")
            return False
    
    def monitor_clipboard(self):
        
        while self.is_running:
            try:
                # Get current clipboard content
                current = pyperclip.paste()
                
                # Check if clipboard has changed
                if current != self.last_clipboard:
                    # Update last known clipboard
                    self.last_clipboard = current
                    
                    # Process if it's a URL
                    if self.is_url(current):
                        self.process_clipboard(current)
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.5)
                
            except:
                pass

    def run(self):
        """Main execution method"""
        try:
            
            # Start monitoring
            self.monitor_clipboard()
            
        except:
            pass
def main():
    cleaner = SilentURLCleaner()
    cleaner.run()

if __name__ == "__main__":
    main()