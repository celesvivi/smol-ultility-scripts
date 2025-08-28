#!/usr/bin/env python3
"""
Robust Silent URL Cleaner
Ensures process visibility in task manager while running silently
Removes tracking parameters from clipboard URLs and converts Twitter posts to fxtwitter

Requirements: pip install pyperclip
"""

import pyperclip
import threading
import time
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import sys
import signal
import logging
import os
from datetime import datetime

class SilentURLCleaner:
    def __init__(self):
        # Set process title for better visibility in task manager
        try:
            if os.name == 'nt':
                import ctypes
                ctypes.windll.kernel32.SetConsoleTitleW("URL Cleaner Service")
        except:
            pass
            
        self.last_clipboard = ""
        self.is_running = True
        self.cleaned_count = 0
        self.start_time = datetime.now()
        self.lock = threading.Lock()
        self.error_count = 0
        
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
            'list', 'index', 'pp', 'source_ve_path', 'ab_channel',
            
            # Amazon
            'tag', 'ref', 'ref_', 'pf_rd_m', 'pf_rd_s', 'pf_rd_r', 'pf_rd_t', 
            'pf_rd_p', 'pf_rd_i', 'pd_rd_i', 'pd_rd_r', 'pd_rd_w', 'pd_rd_wg',
            'linkCode', 'camp', 'creative', 'creativeASIN', 'ascsubtag',
            
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
            'tiktok.com', 'vm.tiktok.com',
            'amazon.com', 'smile.amazon.com',
            'pinterest.com', 'pin.it'
        ]
        
        self.setup_logging()
        self.setup_signal_handlers()
        self.create_status_file()
        
    def create_status_file(self):
        """Create a status file to show the service is running"""
        try:
            status_dir = os.path.join(os.path.expanduser("~"), ".url_cleaner")
            os.makedirs(status_dir, exist_ok=True)
            
            status_file = os.path.join(status_dir, "status.txt")
            with open(status_file, 'w') as f:
                f.write(f"URL Cleaner started at {self.start_time}\n")
                f.write(f"PID: {os.getpid()}\n")
                f.write("Status: Running\n")
        except:
            pass
            
    def update_status_file(self):
        """Update status file with current stats"""
        try:
            status_dir = os.path.join(os.path.expanduser("~"), ".url_cleaner")
            status_file = os.path.join(status_dir, "status.txt")
            
            runtime = datetime.now() - self.start_time
            with open(status_file, 'w') as f:
                f.write(f"URL Cleaner - PID: {os.getpid()}\n")
                f.write(f"Started: {self.start_time}\n")
                f.write(f"Runtime: {runtime}\n")
                f.write(f"URLs cleaned: {self.cleaned_count}\n")
                f.write(f"Errors: {self.error_count}\n")
                f.write("Status: Running\n")
        except:
            pass
        
    def setup_logging(self):
        """Setup logging system"""
        log_dir = os.path.join(os.path.expanduser("~"), ".url_cleaner")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "cleaner.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(message)s',
            handlers=[logging.FileHandler(log_file, mode='a')],
            force=True
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"URL Cleaner started - PID: {os.getpid()}")
        
    def setup_signal_handlers(self):
        """Setup clean shutdown handlers"""
        def cleanup(signum, frame):
            self.cleanup_and_exit()
            
        signal.signal(signal.SIGINT, cleanup)
        signal.signal(signal.SIGTERM, cleanup)
        
    def is_url(self, text):
        """Validate URL format with security checks"""
        if not isinstance(text, str) or len(text) > 2048 or len(text) < 10:
            return False
            
        text = text.strip()
        
        # Block dangerous schemes
        if re.match(r'^(javascript|data|vbscript|file):', text, re.IGNORECASE):
            return False
            
        # Check for valid HTTP/HTTPS URL
        return bool(re.match(
            r'^https?://[a-zA-Z0-9][a-zA-Z0-9\-\.]*[a-zA-Z0-9]/?.+$',
            text, re.IGNORECASE
        ))
    
    def is_supported_platform(self, url):
        """Check if URL is from supported social media platforms"""
        try:
            domain = urlparse(url).netloc.lower()
            domain = domain.replace('www.', '')
            return any(platform in domain for platform in self.supported_domains)
        except:
            return False
    
    def clean_url(self, url):
        """Remove tracking parameters from URL"""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ['http', 'https']:
                return url, []
                
            query_params = parse_qs(parsed.query)
            cleaned_params = {}
            removed = []
            
            for param, values in query_params.items():
                if param.lower() not in self.tracking_params:
                    cleaned_params[param] = values
                else:
                    removed.append(param)
            
            # Rebuild URL
            new_query = urlencode(cleaned_params, doseq=True)
            cleaned_url = urlunparse((
                parsed.scheme, parsed.netloc, parsed.path,
                parsed.params, new_query, parsed.fragment
            ))
            
            return cleaned_url, removed
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"URL cleaning error: {e}")
            return url, []
    
    def convert_twitter_to_fxtwitter(self, url):
        """Convert Twitter/X post URLs to fxtwitter URLs"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace('www.', '')
            
            # Check if it's a Twitter/X domain and contains /status/
            if domain in ['twitter.com', 'x.com', 'mobile.twitter.com'] and '/status/' in parsed.path:
                # Replace domain with fxtwitter.com
                converted_url = urlunparse((
                    parsed.scheme, 'fxtwitter.com', parsed.path,
                    parsed.params, parsed.query, parsed.fragment
                ))
                return converted_url, True
            
            return url, False
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Twitter conversion error: {e}")
            return url, False
    
    def process_clipboard(self):
        """Process clipboard content"""
        try:
            current = pyperclip.paste()
            
            if (not current or current == self.last_clipboard or 
                not isinstance(current, str) or len(current) > 2048):
                return
                
            self.last_clipboard = current
            
            if self.is_url(current) and self.is_supported_platform(current):
                # First, clean tracking parameters
                cleaned, removed = self.clean_url(current)
                
                # Then, convert Twitter posts to fxtwitter
                final_url, was_converted = self.convert_twitter_to_fxtwitter(cleaned)
                
                # Update clipboard if any changes were made
                if (removed and cleaned != current) or was_converted:
                    pyperclip.copy(final_url)
                    self.cleaned_count += 1
                    
                    log_msg = []
                    if removed:
                        log_msg.append(f"removed tracking: {', '.join(removed)}")
                    if was_converted:
                        log_msg.append("converted to fxtwitter")
                    
                    self.logger.info(f"Processed URL - {' | '.join(log_msg)}")
                    
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Clipboard error: {e}")
    
    def monitor_loop(self):
        """Main monitoring loop"""
        self.logger.info("Monitoring started")
        
        while self.is_running:
            try:
                self.process_clipboard()
                
                # Update status every 60 seconds
                if int(time.time()) % 60 == 0:
                    self.update_status_file()
                    
                time.sleep(0.5)
                
            except Exception as e:
                self.error_count += 1
                self.logger.error(f"Monitor loop error: {e}")
                time.sleep(2)
                
                if self.error_count > 50:
                    self.logger.critical("Too many errors, shutting down")
                    break
    
    def cleanup_and_exit(self):
        """Clean shutdown with final status update"""
        self.is_running = False
        self.logger.info(f"Shutting down - Cleaned {self.cleaned_count} URLs")
        
        # Update final status
        try:
            status_file = os.path.join(os.path.expanduser("~"), ".url_cleaner", "status.txt")
            with open(status_file, 'w') as f:
                f.write(f"URL Cleaner - STOPPED\n")
                f.write(f"Last run: {datetime.now()}\n")
                f.write(f"Total cleaned: {self.cleaned_count}\n")
        except:
            pass
            
        sys.exit(0)
    
    def run(self):
        """Main execution method"""
        try:
            # Start background monitoring
            monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            monitor_thread.start()
            
            # Keep main thread alive with minimal activity
            while self.is_running:
                time.sleep(5)  # Check every 5 seconds if we should still be running
                
        except KeyboardInterrupt:
            self.cleanup_and_exit()
        except Exception as e:
            self.logger.error(f"Fatal error: {e}")
            sys.exit(1)

def main():
    """Entry point with proper error handling"""
    # Test clipboard access first
    try:
        pyperclip.paste()
        print("Starting URL Cleaner service...")
        print(f"Process ID: {os.getpid()}")
        print("Look for 'python.exe' or 'pythonw.exe' in Task Manager")
        print("Press Ctrl+C to stop")
        
        # Brief delay to see the message before going silent
        time.sleep(2)
        
    except ImportError:
        print("Error: pyperclip not installed")
        print("Run: pip install pyperclip")
        sys.exit(1)
    except Exception as e:
        print(f"Clipboard access failed: {e}")
        sys.exit(1)
    
    # Start the service
    cleaner = SilentURLCleaner()
    cleaner.run()

if __name__ == "__main__":
    main()
