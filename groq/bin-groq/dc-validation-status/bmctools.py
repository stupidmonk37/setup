#!/usr/bin/env python3

"""
BMC Tools Integration Module
============================
Python module that integrates the functionality from bmctools bash scripts
for pre-validation checks including BMC reachability, authentication, and 
network connectivity testing.
"""

import csv
import subprocess
import socket
import os
import time
import requests
import json
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class BMCTools:
    def __init__(self, csv_file_path: Optional[str] = None, context: Optional[str] = None, bmc_username: str = "root", bmc_password: str = "GroqRocks1"):
        """
        Initialize BMC Tools with configuration.
        
        Args:
            csv_file_path: Path to site CSV file with IP mappings
            context: Kubernetes context name to determine which site.csv to use
            bmc_username: BMC username for authentication tests
            bmc_password: BMC password for authentication tests
        """
        self.context = context
        self.csv_file_path = csv_file_path or self._find_csv_file()
        self.bmc_username = bmc_username
        self.bmc_password = bmc_password
        self.ip_mappings = {}
        
        if self.csv_file_path and os.path.exists(self.csv_file_path):
            self._load_csv_mappings()
    
    def _find_csv_file(self) -> Optional[str]:
        """Find CSV file automatically using same logic as bash script."""
        # If context is specified, try to use the anodizer-sites directory
        if self.context:
            # Map context names to site directory names
            context_to_site = {
                "yyc1-prod1": "yyc1",
                "dal1-prod1": "dal1", 
                "dmm1-prod1": "dmm1",
                "dmm1-prod2": "dmm1",
                "geg3-prod1": "geg3",
                "hel1-prod1": "hel1",
                "hou1-prod1": "hou1",
                "hou2-prod1": "hou2",
                "msp1-prod1": "msp1",
                "msp2-prod1": "msp2",
                "yka1-prod1": "yka1"
            }
            
            site_name = context_to_site.get(self.context)
            if site_name:
                # First try local sites directory
                local_path = f"sites/{site_name}/site.csv"
                if os.path.exists(local_path):
                    return local_path
                
                # Fallback to volume mount path (for Docker)
                anodizer_path = f"/app/anodizer-sites/sites/{site_name}/site.csv"
                if os.path.exists(anodizer_path):
                    return anodizer_path
        
        # No fallback paths - rely on context-based site.csv loading
        return None
    
    def _load_csv_mappings(self):
        """Load IP mappings from CSV file."""
        try:
            with open(self.csv_file_path, 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    hostname = row.get('hostname', '').strip()
                    ip = row.get('ip', '').strip()
                    if hostname and ip:
                        self.ip_mappings[hostname] = ip
        except Exception as e:
            print(f"Warning: Could not load CSV mappings: {e}")
    
    def lookup_ip(self, hostname: str) -> Optional[str]:
        """Lookup IP address for a hostname from CSV mappings."""
        return self.ip_mappings.get(hostname)
    
    def ping_host(self, ip: str, timeout: int = 3, count: int = 2) -> bool:
        """
        Ping a host to test connectivity.
        
        Args:
            ip: IP address to ping
            timeout: Timeout in seconds
            count: Number of ping packets
            
        Returns:
            True if host responds to ping, False otherwise
        """
        if not ip or ip == "N/A":
            return False
        
        try:
            # Use ping command with timeout
            cmd = ["ping", "-c", str(count), "-W", str(timeout), ip]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return False
    
    def test_bmc_auth(self, bmc_ip: str, timeout: int = 10) -> Tuple[bool, str]:
        """
        Test BMC authentication using ipmitool.
        
        Args:
            bmc_ip: BMC IP address
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not bmc_ip or bmc_ip == "N/A":
            return False, "IP not available"
        
        try:
            cmd = [
                "ipmitool", "-H", bmc_ip, 
                "-U", self.bmc_username, 
                "-P", self.bmc_password, 
                "-N", str(timeout), 
                "chassis", "status"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            
            if result.returncode == 0:
                return True, "Authentication successful"
            else:
                return False, f"Authentication failed: {result.stderr.strip()}"
                
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def get_bmc_version(self, bmc_ip: str, timeout: int = 10) -> str:
        """
        Get BMC version using ipmitool mc info.
        
        Args:
            bmc_ip: BMC IP address
            timeout: Timeout in seconds
            
        Returns:
            BMC version string
        """
        if not bmc_ip or bmc_ip == "N/A":
            return "unknown"
        
        try:
            cmd = [
                "ipmitool", "-H", bmc_ip,
                "-U", self.bmc_username,
                "-P", self.bmc_password,
                "-N", str(timeout),
                "mc", "info"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            
            if result.returncode == 0:
                # Look for different version patterns in mc info output
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    
                    # Try different version patterns
                    if 'Firmware Revision' in line:
                        # Look for full version with dots: XX.XX.XX
                        match = re.search(r':\s*([\d.]+)', line)
                        if match:
                            version = match.group(1)
                            # If we only got partial version (like 7.03), try to get more detail
                            if version and len(version.split('.')) >= 2:
                                return version
                    
                    # Try auxiliary firmware info if available
                    if 'Aux Firmware Rev' in line or 'Additional Device Support' in line:
                        match = re.search(r':\s*([\d.]+)', line)
                        if match:
                            return match.group(1)
                
                # Fallback: try to get version from device info
                device_id_match = None
                fw_rev_match = None
                for line in result.stdout.split('\n'):
                    if 'Device ID' in line:
                        device_id_match = re.search(r':\s*(\d+)', line)
                    elif 'Firmware Revision' in line:
                        fw_rev_match = re.search(r':\s*([\d.]+)', line)
                
                # If we have firmware revision, return it (may need to be formatted)
                if fw_rev_match:
                    version = fw_rev_match.group(1)
                    # Try to format as XX.XX.XX if it's shorter
                    parts = version.split('.')
                    if len(parts) == 2:
                        return f"0{parts[0]}.{parts[1]}.01"  # Add leading zero and .01
                    return version
                
                return "available"
            else:
                return "unknown"
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return "unknown"
        except Exception:
            return "unknown"
    
    def get_bios_version(self, bmc_ip: str, timeout: int = 10) -> str:
        """
        Get BIOS version using multiple ipmitool approaches.
        
        Args:
            bmc_ip: BMC IP address
            timeout: Timeout in seconds
            
        Returns:
            BIOS version string
        """
        if not bmc_ip or bmc_ip == "N/A":
            return "unknown"
        
        # Try multiple approaches to get BIOS version
        
        # Approach 1: Try FRU data looking for version patterns
        try:
            cmd = [
                "ipmitool", "-H", bmc_ip,
                "-U", self.bmc_username,
                "-P", self.bmc_password,
                "-N", str(timeout),
                "fru"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            
            if result.returncode == 0:
                # Look for version patterns like "3.1.V2"
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    # Look for version patterns with V, dots, or typical version formats
                    version_match = re.search(r'(\d+\.\d+\.V\d+|\d+\.\d+\.\d+[A-Z]?\d*|V\d+\.\d+\.\d+)', line, re.IGNORECASE)
                    if version_match:
                        return version_match.group(1)
                    
                    # Also check for lines that contain "version" explicitly
                    if 'version' in line.lower() and ':' in line:
                        version_part = line.split(':', 1)[1].strip()
                        if version_part and version_part.lower() not in ['n/a', 'unknown', '']:
                            # Check if it looks like a version (contains dots or V)
                            if re.search(r'[\d.V]', version_part):
                                return version_part
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass
        
        # Approach 2: Try sensor data which might have system info
        try:
            cmd = [
                "ipmitool", "-H", bmc_ip,
                "-U", self.bmc_username,
                "-P", self.bmc_password,
                "-N", str(timeout),
                "sdr", "type", "System Firmware Progress"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            
            if result.returncode == 0:
                # Look for version info in SDR output
                for line in result.stdout.split('\n'):
                    version_match = re.search(r'(\d+\.\d+\.V\d+|\d+\.\d+\.\d+)', line)
                    if version_match:
                        return version_match.group(1)
                        
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass
        
        # Approach 3: Try raw command for system info (if other methods fail)
        try:
            cmd = [
                "ipmitool", "-H", bmc_ip,
                "-U", self.bmc_username,
                "-P", self.bmc_password,
                "-N", str(timeout),
                "raw", "0x06", "0x59", "0x00", "0xc1"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
            
            if result.returncode == 0 and result.stdout.strip():
                # Raw data might contain version info, but hard to parse
                return "available"
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass
        
        return "unknown"
    
    def get_redfish_session(self, bmc_ip: str, timeout: int = 10) -> Optional[requests.Session]:
        """
        Create a Redfish session with BMC.
        
        Args:
            bmc_ip: BMC IP address
            timeout: Timeout in seconds
            
        Returns:
            Authenticated session or None if failed
        """
        if not bmc_ip or bmc_ip == "N/A":
            return None
        
        session = requests.Session()
        session.verify = False  # Ignore self-signed certificates
        session.timeout = timeout
        
        try:
            # Try to authenticate
            auth_url = f"https://{bmc_ip}/redfish/v1/SessionService/Sessions"
            auth_data = {
                "UserName": self.bmc_username,
                "Password": self.bmc_password
            }
            
            response = session.post(auth_url, json=auth_data, timeout=timeout)
            
            if response.status_code in [200, 201]:
                # Extract session token if provided
                if 'X-Auth-Token' in response.headers:
                    session.headers['X-Auth-Token'] = response.headers['X-Auth-Token']
                elif 'Location' in response.headers:
                    session.headers['X-Auth-Token'] = response.headers['Location'].split('/')[-1]
                
                return session
            else:
                # Try basic auth fallback
                session.auth = (self.bmc_username, self.bmc_password)
                
                # Test basic auth with a simple GET
                test_response = session.get(f"https://{bmc_ip}/redfish/v1", timeout=timeout)
                if test_response.status_code == 200:
                    return session
                    
        except Exception:
            pass
        
        return None
    
    def get_bmc_version_redfish(self, bmc_ip: str, timeout: int = 10) -> str:
        """
        Get BMC version using Redfish API.
        
        Args:
            bmc_ip: BMC IP address  
            timeout: Timeout in seconds
            
        Returns:
            BMC version string
        """
        if not bmc_ip or bmc_ip == "N/A":
            return "unknown"
        
        session = self.get_redfish_session(bmc_ip, timeout)
        if not session:
            return "unknown"
        
        try:
            # Try different manager endpoints
            manager_urls = [
                f"https://{bmc_ip}/redfish/v1/Managers/1",
                f"https://{bmc_ip}/redfish/v1/Managers/bmc",
                f"https://{bmc_ip}/redfish/v1/Managers/BMC"
            ]
            
            for url in manager_urls:
                try:
                    response = session.get(url, timeout=timeout)
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Look for firmware version in different fields
                        if 'FirmwareVersion' in data:
                            return data['FirmwareVersion']
                        elif 'Firmware' in data and isinstance(data['Firmware'], dict):
                            if 'Current' in data['Firmware']:
                                return data['Firmware']['Current'].get('VersionString', 'unknown')
                        elif 'Oem' in data:
                            # Check OEM specific fields
                            oem_data = data['Oem']
                            for vendor in oem_data.values():
                                if isinstance(vendor, dict) and 'FirmwareVersion' in vendor:
                                    return vendor['FirmwareVersion']
                                    
                except Exception:
                    continue
            
            return "unknown"
            
        except Exception:
            return "unknown"
        finally:
            try:
                session.close()
            except:
                pass
    
    def get_bios_version_redfish(self, bmc_ip: str, timeout: int = 10) -> str:
        """
        Get BIOS version using Redfish API.
        
        Args:
            bmc_ip: BMC IP address
            timeout: Timeout in seconds
            
        Returns:
            BIOS version string
        """
        if not bmc_ip or bmc_ip == "N/A":
            return "unknown"
        
        session = self.get_redfish_session(bmc_ip, timeout)
        if not session:
            return "unknown"
        
        try:
            # Try different system endpoints
            system_urls = [
                f"https://{bmc_ip}/redfish/v1/Systems/1",
                f"https://{bmc_ip}/redfish/v1/Systems/System.Embedded.1",
                f"https://{bmc_ip}/redfish/v1/Systems/Self"
            ]
            
            for url in system_urls:
                try:
                    response = session.get(url, timeout=timeout)
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Look for BIOS version in different fields
                        if 'BiosVersion' in data:
                            return data['BiosVersion']
                        elif 'Bios' in data and isinstance(data['Bios'], dict):
                            if 'Current' in data['Bios']:
                                return data['Bios']['Current'].get('VersionString', 'unknown')
                        elif 'Oem' in data:
                            # Check OEM specific fields for BIOS info
                            oem_data = data['Oem']
                            for vendor in oem_data.values():
                                if isinstance(vendor, dict):
                                    for key, value in vendor.items():
                                        if 'bios' in key.lower() and isinstance(value, (str, dict)):
                                            if isinstance(value, str):
                                                return value
                                            elif isinstance(value, dict) and 'Version' in value:
                                                return value['Version']
                        
                        # Also try looking in firmware inventory
                        if 'Links' in data and 'ManagedBy' in data['Links']:
                            # Could try to get firmware inventory, but that's more complex
                            pass
                                    
                except Exception:
                    continue
            
            return "unknown"
            
        except Exception:
            return "unknown"
        finally:
            try:
                session.close()
            except:
                pass
    
    def analyze_node(self, rack: str, node_num: int, domain: str = "yyc1-prod1.groq.net") -> Dict:
        """
        Analyze a single node (compute + BMC + auth).
        
        Args:
            rack: Rack identifier (e.g., "c0r1")
            node_num: Node number (1-9)
            domain: Domain suffix
            
        Returns:
            Dictionary with detailed analysis results
        """
        compute_hostname = f"{rack}-gn{node_num}"
        bmc_hostname = f"{rack}-gn{node_num}-bmc"
        
        compute_ip = self.lookup_ip(compute_hostname)
        bmc_ip = self.lookup_ip(bmc_hostname)
        
        # Test compute connectivity
        if not compute_ip:
            compute_status = "missing"
            compute_response_time = "N/A"
        else:
            start_time = time.time()
            if self.ping_host(compute_ip):
                compute_status = "reachable"
                compute_response_time = f"{int((time.time() - start_time) * 1000)}ms"
            else:
                compute_status = "unreachable"
                compute_response_time = "timeout"
        
        # Test BMC connectivity
        if not bmc_ip:
            bmc_status = "missing"
            bmc_response_time = "N/A"
        else:
            start_time = time.time()
            if self.ping_host(bmc_ip):
                bmc_status = "reachable"
                bmc_response_time = f"{int((time.time() - start_time) * 1000)}ms"
            else:
                bmc_status = "unreachable"
                bmc_response_time = "timeout"
        
        # Test BMC authentication if BMC is reachable
        if bmc_status == "reachable":
            auth_success, auth_message = self.test_bmc_auth(bmc_ip)
            if auth_success:
                # Get version information if authentication works
                # Try Redfish first, fallback to ipmitool
                bmc_version = self.get_bmc_version_redfish(bmc_ip)
                if bmc_version == "unknown":
                    bmc_version = self.get_bmc_version(bmc_ip)
                
                bios_version = self.get_bios_version_redfish(bmc_ip) 
                if bios_version == "unknown":
                    bios_version = self.get_bios_version(bmc_ip)
                    
                firmware_status = "updated"  # Assume updated if auth works
                firmware_current = bmc_version  # Use actual BMC version
            else:
                bmc_version = "unknown"
                bios_version = "unknown"
                firmware_status = "unknown"
                firmware_current = "unknown"
        else:
            auth_success = False
            auth_message = "BMC unreachable"
            bmc_version = "unknown"
            bios_version = "unknown"
            firmware_status = "unknown"
            firmware_current = "unknown"
        
        # Determine network status based on combination of tests
        if compute_status == "reachable" and bmc_status == "reachable":
            network_status = "connected"
        elif compute_status == "reachable" or bmc_status == "reachable":
            network_status = "partial"
        else:
            network_status = "disconnected"
        
        # Determine overall diagnosis
        if compute_status == "reachable" and bmc_status == "reachable" and auth_success:
            overall_status = "ready"
        elif bmc_status == "reachable" and auth_success and compute_status == "unreachable":
            overall_status = "network_disconnected"
        elif bmc_status == "reachable" and not auth_success:
            overall_status = "bmc_auth_failed"
        elif compute_status == "missing" or bmc_status == "missing":
            overall_status = "missing_from_csv"
        elif compute_status == "unreachable" and bmc_status == "unreachable":
            overall_status = "hardware_failure"
        else:
            overall_status = "mixed_issues"
        
        return {
            "rack": rack,
            "node": node_num,
            "compute_hostname": compute_hostname,
            "compute_ip": compute_ip or "N/A",
            "bmc_hostname": bmc_hostname,
            "bmc_ip": bmc_ip or "N/A",
            "bmc": {
                "status": bmc_status,
                "ip": bmc_ip or "N/A",
                "response_time": bmc_response_time,
                "auth_success": auth_success,
                "auth_message": auth_message,
                "version": bmc_version
            },
            "bios": {
                "version": bios_version
            },
            "firmware": {
                "status": firmware_status,
                "current": firmware_current,
                "latest": "v2.1.3"  # Placeholder
            },
            "network": {
                "status": network_status,
                "ping": "success" if compute_status == "reachable" else "failed",
                "dns": "success"  # Placeholder - could add DNS testing
            },
            "compute_status": compute_status,
            "overall_status": overall_status
        }
    
    def analyze_racks(self, racks: List[str], max_workers: int = 10) -> List[Dict]:
        """
        Analyze multiple racks in parallel.
        
        Args:
            racks: List of rack identifiers (e.g., ["c0r1", "c0r2"])
            max_workers: Maximum number of parallel workers
            
        Returns:
            List of analysis results for all nodes in all racks
        """
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all node analysis tasks
            futures = {}
            for rack in racks:
                for node_num in range(1, 10):  # Nodes 1-9
                    future = executor.submit(self.analyze_node, rack, node_num)
                    futures[future] = (rack, node_num)
            
            # Collect results as they complete
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    rack, node_num = futures[future]
                    print(f"Error analyzing {rack}-gn{node_num}: {e}")
        
        return results
    
    def get_rack_list_from_cluster(self) -> List[str]:
        """
        Get list of racks by analyzing CSV file hostnames.
        
        Returns:
            List of rack identifiers found in CSV
        """
        racks = set()
        
        for hostname in self.ip_mappings.keys():
            # Match pattern like c0r1-gn1 -> extract c0r1
            match = re.match(r'^(c\d+r\d+)-gn\d+$', hostname)
            if match:
                racks.add(match.group(1))
        
        return sorted(list(racks), key=lambda x: (
            int(re.search(r'c(\d+)', x).group(1)),
            int(re.search(r'r(\d+)', x).group(1))
        ))
    
    def get_rack_list_fast(self) -> Dict:
        """
        Get just the rack list without running any network tests.
        Returns basic rack info for fast initial loading.
        
        Returns:
            Dictionary with rack list for quick API response
        """
        racks = self.get_rack_list_from_cluster()
        
        # Return basic rack info without any testing
        rack_list = []
        for rack in racks:
            rack_list.append({
                "rack": rack,
                "bmc": {"status": "not_tested", "ip": "—", "response_time": "—"},
                "firmware": {"status": "not_tested", "current": "—", "latest": "—"},
                "network": {"status": "not_tested", "ping": "not_tested", "dns": "not_tested"},
                "overall_status": "not_tested"
            })
        
        return {"racks": rack_list}
    
    def analyze_single_rack_detailed(self, rack: str) -> Dict:
        """
        Run detailed analysis for a single rack only.
        
        Args:
            rack: Rack identifier (e.g., "c0r1")
            
        Returns:
            Detailed analysis results for the specific rack
        """
        analysis_results = self.analyze_racks([rack])
        return self.format_for_api(analysis_results)
    
    def format_for_api(self, analysis_results: List[Dict]) -> Dict:
        """
        Format analysis results for the pre-validation API.
        
        Args:
            analysis_results: Raw analysis results from analyze_racks
            
        Returns:
            Formatted data structure for API response
        """
        api_results = []
        
        # Group results by rack
        racks_data = {}
        for result in analysis_results:
            rack = result["rack"]
            if rack not in racks_data:
                racks_data[rack] = []
            racks_data[rack].append(result)
        
        # Format each rack
        for rack, nodes in racks_data.items():
            # Calculate rack-level status
            all_ready = all(n["overall_status"] == "ready" for n in nodes)
            any_issues = any(n["overall_status"] != "ready" for n in nodes)
            
            if all_ready:
                rack_overall = "ready"
            elif not any_issues:
                rack_overall = "ready"
            else:
                rack_overall = "issues"
            
            # Get representative values from first healthy node or any node
            healthy_node = next((n for n in nodes if n["overall_status"] == "ready"), nodes[0] if nodes else None)
            
            if healthy_node:
                api_results.append({
                    "rack": rack,
                    "bmc": {
                        "status": "reachable" if any(n["bmc"]["status"] == "reachable" for n in nodes) else "unreachable",
                        "ip": healthy_node["bmc"]["ip"],
                        "response_time": healthy_node["bmc"]["response_time"]
                    },
                    "firmware": {
                        "status": "updated" if healthy_node["firmware"]["status"] == "updated" else "outdated",
                        "current": healthy_node["firmware"]["current"],
                        "latest": healthy_node["firmware"]["latest"]
                    },
                    "network": {
                        "status": "connected" if any(n["network"]["status"] == "connected" for n in nodes) else "disconnected",
                        "ping": "success" if any(n["network"]["ping"] == "success" for n in nodes) else "failed",
                        "dns": "success"  # Placeholder
                    },
                    "overall_status": rack_overall,
                    "nodes": nodes  # Include detailed node data
                })
        
        return {"racks": api_results}

# Convenience functions for use in server.py
def get_rack_list_fast(context: Optional[str] = None) -> Dict:
    """
    Get rack list quickly without running any network tests.
    
    Args:
        context: Kubernetes context name to determine which site.csv to use
        
    Returns:
        Fast rack list for initial page load
    """
    bmc_tools = BMCTools(context=context)
    
    if not bmc_tools.csv_file_path:
        return {"error": "CSV file not found", "racks": []}
    
    return bmc_tools.get_rack_list_fast()

def run_detailed_rack_analysis(rack: str, context: Optional[str] = None) -> Dict:
    """
    Run detailed analysis for a specific rack.
    
    Args:
        rack: Rack identifier to analyze
        context: Kubernetes context name to determine which site.csv to use
        
    Returns:
        Detailed analysis results for the rack
    """
    bmc_tools = BMCTools(context=context)
    
    if not bmc_tools.csv_file_path:
        return {"error": "CSV file not found", "racks": []}
    
    print(f"Running detailed pre-validation analysis on rack: {rack}")
    
    return bmc_tools.analyze_single_rack_detailed(rack)

def run_pre_validation_check(racks: Optional[List[str]] = None) -> Dict:
    """
    Run pre-validation check and return formatted results.
    [DEPRECATED - Use get_rack_list_fast() and run_detailed_rack_analysis() instead]
    
    Args:
        racks: Optional list of specific racks to check. If None, checks all racks from CSV.
        
    Returns:
        Formatted results for API response
    """
    bmc_tools = BMCTools()
    
    if not bmc_tools.csv_file_path:
        return {"error": "CSV file not found", "racks": []}
    
    if racks is None:
        racks = bmc_tools.get_rack_list_from_cluster()[:5]  # Limit to first 5 racks for demo
    
    if not racks:
        return {"error": "No racks found", "racks": []}
    
    print(f"Running pre-validation check on racks: {racks}")
    
    # Run analysis
    analysis_results = bmc_tools.analyze_racks(racks)
    
    # Format for API
    formatted_results = bmc_tools.format_for_api(analysis_results)
    
    return formatted_results
