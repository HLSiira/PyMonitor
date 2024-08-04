#!/usr/bin/env python3

import os
import sys
import socket
import requests
import subprocess
import argparse
import json
import tempfile
import threading
import time
import re

TWA_VERSION = "1.11.0"

TWA_TIMEOUT = int(os.getenv("TWA_TIMEOUT", 5))
TWA_USER_AGENT = os.getenv("TWA_USER_AGENT", "Mozilla/5.0")
TWA_CURLOPTS = os.getenv("TWA_CURLOPTS", "").split()

TWA_CODES = {
    # Stage 01
    "TWA-0001": "Expected port 443 to be open, but it isn't",
    "TWA-0101": "HTTP redirects to HTTPS using a 302",
    "TWA-0102": "HTTP redirects to HTTP (not secure)",
    "TWA-0103": "HTTP doesn't redirect at all",
    # Stage 02
    "TWA-0201": "Skipping security checks due to no secure channel",
    "TWA-0202": "Strict-Transport-Security max-age is less than 6 months",
    "TWA-0203": "Strict-Transport-Security, but no includeSubDomains",
    "TWA-0204": "Strict-Transport-Security, but no preload",
    "TWA-0205": "Strict-Transport-Security missing",
    "TWA-0206": "X-Frame-Options is 'sameorigin', consider 'deny'",
    "TWA-0207": "X-Frame-Options is 'allow-from', consider 'deny' or 'none'",
    "TWA-0208": "X-Frame-Options missing",
    "TWA-0209": "X-Content-Type-Options missing",
    "TWA-0210": "X-XSS-Protection is '0'; XSS filtering disabled",
    "TWA-0211": "X-XSS-Protection sanitizes but doesn't block, consider mode=block?",
    "TWA-0212": "X-XSS-Protection missing",
    "TWA-0213": "Referrer-Policy specifies '{rp}', consider 'no-referrer'?",
    "TWA-0214": "Referrer-Policy missing",
    "TWA-0215": "Content-Security-Policy 'default-src' is '{csp_default_src}'",
    "TWA-0216": "Content-Security-Policy 'default-src' is missing",
    "TWA-0217": "Content-Security-Policy has one or more 'unsafe-inline' policies",
    "TWA-0218": "Content-Security-Policy has one or more 'unsafe-eval' policies",
    "TWA-0219": "Content-Security-Policy missing",
    "TWA-0220": "Feature-Policy missing",
    "TWA-0221": "Expect-CT missing 'enforce' directive",
    "TWA-0222": "Expect-CT missing 'report-uri' directive",
    "TWA-0223": "Expect-CT requires missing 'max-age' directive",
    "TWA-0224": "'Access-Control-Allow-Origin' field '*' allows resources to be accessible by any domain.",
    "TWA-0225": "'Access-Control-Allow-Origin' field 'null' allows the 'Origin' header to be crafted to grant access to resources on this domain.",
    "TWA-0226": "'Access-Control-Allow-Origin' header is not configured properly.",
    "TWA-0227": "'Access-Control-Allow-Credentials' value is set to 'false'.",
    "TWA-0228": "'Access-Control-Allow-Credentials' header is not configured properly.",
    "TWA-0229": "'Cross-Origin-Embedder-Policy' allows cross-origin resources to be fetched without giving explicit permission.",
    "TWA-0230": "'Cross-Origin-Opener-Policy' allows the document to be added to its opener's browsing context group.",
    # Stage 03
    "TWA-0301": "Site sends 'Server' with what looks like a version tag: {server}",
    "TWA-0302": "Site sends a long 'Server', probably disclosing version info: {server}",
    "TWA-0303": "Site sends '{badheader}', probably disclosing version info: '{content}'",
    # Stage 04
    "TWA-0401": "SCM repository being served at: {url}",
    "TWA-0402": "Possible SCM repository being served (maybe protected?) at: {url}",
    "TWA-0403": "Environment file being served at: {url}",
    "TWA-0404": "Possible environment file being served (maybe protected?) at: {url}",
    "TWA-0405": "Config file being served at: {url}",
    "TWA-0406": "Possible config file being served (maybe protected?) at: {url}",
    "TWA-0407": "Package management file being served at: {url}",
    "TWA-0408": "Possible package management file being served (maybe protected?) at: {url}",
    "TWA-0409": "Build file being served at: {url}",
    "TWA-0410": "Possible build file being served (maybe protected?) at: {url}",
    # Stage 05
    "TWA-0501": "No robots file found at: {domain}/robots.txt",
    "TWA-0502": "robots.txt lists what looks like an admin panel",
    "TWA-0503": "robots.txt lists what looks like CGI scripts",
    "TWA-0504": "No security file found at: {domain}/.well-known/security.txt",
    # Stage 06
    "TWA-0601": "No CAA records found",
    "TWA-0602": "Domain doesn't specify any valid issuers",
    "TWA-0603": "Domain explicitly disallows all issuers",
    "TWA-0604": "Domain doesn't specify any violation reporting endpoints",
    # Stage 07
    "TWA-0701": "Domain is listening on a development/backend port {dev_port} ({dev_port_comment})",
    # Stage 08
    "TWA-0801": "cookie '{cookie_name}' has 'secure' but no 'httponly' flag",
    "TWA-0802": "cookie '{cookie_name}' has no 'secure' flag",
    "TWA-0803": "cookie '{cookie_name}' has SameSite set to 'lax'",
    "TWA-0804": "cookie '{cookie_name}' has SameSite set to 'none' or is not set properly",
    "TWA-0805": "cookie '{cookie_name}' has missing or empty 'SameSite' flag",
    "TWA-0806": "cookie '{cookie_name}' must contain a 'Domain' attribute",
    "TWA-0807": "cookie '{cookie_name}' must not contain a 'Domain' attribute",
    "TWA-0808": "cookie '{cookie_name}' must contain a 'Path' attribute",
    "TWA-0809": "cookie '{cookie_name}' 'Domain' attribute must match the domain being tested",
    "TWA-0810": "cookie '{cookie_name}' 'Path' attribute must contain a value of '/'",
}


class TinyWebsiteAuditor:
    def __init__(
        self,
        domain,
        verbose=False,
        disableportscan=False,
    ):
        self.domain = domain.lower()
        self.verbose = verbose
        self.disableportscan = disableportscan
        self.no_https = False
        self.score = 100
        self.npasses = 0
        self.nmehs = 0
        self.nfailures = 0
        self.nunknowns = 0
        self.nskips = 0
        self.totally_screwed = 0

    def log(self, level, message):
        if self.verbose:
            print(f"[{level}] {message}")

    def die(self, message):
        print(f"Error: {message}", file=sys.stderr)
        exit(1)

    def warn(self, message):
        print(f"Warn: {message}", file=sys.stderr)

    def output(self, status, message, code=None):
        print(f"\t{status}({self.domain}): {message}")

    def probe(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(TWA_TIMEOUT)
            result = sock.connect_ex((self.domain, port))
            return result == 0

    def fetch(self, url, headers_only=False):
        headers = {
            "User-Agent": TWA_USER_AGENT,
        }
        try:
            response = (
                requests.head(url, headers=headers, timeout=TWA_TIMEOUT)
                if headers_only
                else requests.get(url, headers=headers, timeout=TWA_TIMEOUT)
            )
            return response
        except requests.RequestException as e:
            self.log("ERROR", f"Failed to fetch {url}: {e}")
            return None

    ##############################################################################80

    # Stage 0: The server should support HTTPS.
    #
    # Checks:
    # * Connecting via port 443 should yield a valid certificate and HTTP connection.
    #
    # This test is a little special, in that it sets "no_https" if it fails. Stage 2
    # checks "no_https" and doesn't run if it's set, as security headers are pointless over HTTP.
    # As such, failure in this stage is marked as "FATAL".
    def stage_0_has_https(self):
        self.log("INFO", "Stage 0: Server supports HTTPS")

        if not self.probe(443):
            self.output("FATAL", TWA_CODES["TWA-0001"], "TWA-0001")
            self.no_https = True

    ##############################################################################80

    # Stage 1: HTTP should be redirected to HTTPS; no exceptions.
    #
    # Checks:
    # * Connecting via port 80 should return HTTP 301 with a HTTPS location.
    def stage_1_redirection(self):
        self.log("INFO", "Stage 1: HTTP -> HTTPS redirection")
        headers = self.fetch(f"http://{self.domain}", headers_only=True)
        if headers is None:
            return

        location = self.get_header(headers.headers, "Location")
        response_code = headers.status_code

        if location.startswith("https"):
            if response_code in [301, 308]:
                self.output("PASS", f"HTTP redirects to HTTPS using a {response_code}")
            elif response_code in [302, 307]:
                self.output("MEH", TWA_CODES["TWA-0101"], "TWA-0101")
            else:
                self.output(
                    "UNK",
                    f"HTTP sends an HTTPS location but with a weird response code: {response_code}",
                )
        elif location.startswith("http"):
            self.output("FAIL", TWA_CODES["TWA-0102"], "TWA-0102")
        else:
            self.output("FAIL", TWA_CODES["TWA-0103"], "TWA-0103")

    ##############################################################################80
    # Stage 2: The server should specify a decent set of security headers.
    #
    # Checks:
    # * Strict-Transport-Security should specify a max-age
    # * X-Frame-Options should be "deny"
    # * X-Content-Type-Options should be "nosniff"
    # * X-XSS-Protection should be "1; mode=block"
    # * Referrer-Policy should be "no-referrer"
    # * Content-Security-Policy should be whatever awful policy string is the most secure.
    #
    # TODO: Add Feature-Policy?
    def stage_2_security_headers(self, headers):
        self.log("INFO", "Checking security headers")
        if self.no_https:
            self.output("FATAL", TWA_CODES["TWA-0201"], "TWA-0201")
            return
        response = self.fetch(f"https://{self.domain}", headers_only=True)
        if response is None:
            return
        headers = response.headers

        # Check for Strict-Transport-Security
        sts = headers.get("Strict-Transport-Security", "")
        if sts:
            max_age = int(sts.split("max-age=")[-1].split(";")[0])
            if max_age >= 15768000:
                self.output(
                    "PASS", "Strict-Transport-Security max-age is at least 6 months"
                )
            else:
                self.output("MEH", TWA_CODES["TWA-0202"], "TWA-0202")
            if "includeSubDomains" in sts:
                self.output(
                    "PASS", "Strict-Transport-Security specifies includeSubDomains"
                )
            else:
                self.output("MEH", TWA_CODES["TWA-0203"], "TWA-0203")
            if "preload" in sts:
                self.output("PASS", "Strict-Transport-Security specifies preload")
            else:
                self.output("MEH", TWA_CODES["TWA-0204"], "TWA-0204")
        else:
            self.output("FAIL", TWA_CODES["TWA-0205"], "TWA-0205")

        # Check for X-Frame-Options
        xfo = headers.get("X-Frame-Options", "").lower()
        if xfo:
            if xfo == "deny":
                self.output("PASS", "X-Frame-Options is 'deny'")
            elif xfo == "sameorigin":
                self.output("MEH", TWA_CODES["TWA-0206"], "TWA-0206")
            elif "allow-from" in xfo:
                self.output("MEH", TWA_CODES["TWA-0207"], "TWA-0207")
            else:
                self.output("UNK", f"X-Frame-Options set to something weird: {xfo}")
        else:
            self.output("FAIL", TWA_CODES["TWA-0208"], "TWA-0208")

        # Check for X-Content-Type-Options
        xcto = headers.get("X-Content-Type-Options", "").lower()
        if xcto:
            if xcto == "nosniff":
                self.output("PASS", "X-Content-Type-Options is 'nosniff'")
            else:
                self.output(
                    "UNK", f"X-Content-Type-Options set to something weird: {xcto}"
                )
        else:
            self.output("FAIL", TWA_CODES["TWA-0209"], "TWA-0209")

        # Check for X-XSS-Protection
        xxp = headers.get("X-XSS-Protection", "").lower()
        if xxp:
            if xxp == "0":
                self.output("FAIL", TWA_CODES["TWA-0210"], "TWA-0210")
            elif xxp.startswith("1"):
                if "mode=block" in xxp:
                    self.output("PASS", "X-XSS-Protection specifies mode=block")
                else:
                    self.output("MEH", TWA_CODES["TWA-0211"], "TWA-0211")
        else:
            self.output("FAIL", TWA_CODES["TWA-0212"], "TWA-0212")

        # Check for Referrer-Policy
        rp = headers.get("Referrer-Policy", "").lower()
        if rp:
            if rp == "no-referrer":
                self.output("PASS", "Referrer-Policy specifies 'no-referrer'")
            elif rp in [
                "unsafe-url",
                "no-referrer-when-downgrade",
                "origin",
                "origin-when-cross-origin",
                "same-origin",
                "strict-origin",
            ]:
                self.output("MEH", TWA_CODES["TWA-0213"], "TWA-0213")
        else:
            self.output("FAIL", TWA_CODES["TWA-0214"], "TWA-0214")

        # Check for Content-Security-Policy
        csp = headers.get("Content-Security-Policy", "")
        csp_default_src = [
            x.split()[-1] for x in csp.split(";") if x.strip().startswith("default-src")
        ]
        if csp:
            if csp_default_src:
                if csp_default_src[0] == "'none'":
                    self.output(
                        "PASS", "Content-Security-Policy 'default-src' is 'none'"
                    )
                else:
                    self.output("MEH", TWA_CODES["TWA-0215"], "TWA-0215")
            else:
                self.output("FAIL", TWA_CODES["TWA-0216"], "TWA-0216")
            if "unsafe-inline" in csp:
                self.output("FAIL", TWA_CODES["TWA-0217"], "TWA-0217")
            if "unsafe-eval" in csp:
                self.output("FAIL", TWA_CODES["TWA-0218"], "TWA-0218")
        else:
            self.output("FAIL", TWA_CODES["TWA-0219"], "TWA-0219")

        # Check for Feature-Policy
        fp = headers.get("Feature-Policy", "")
        if fp:
            self.output("SKIP", "Feature-Policy checks not implemented yet")
        else:
            self.output("FAIL", TWA_CODES["TWA-0220"], "TWA-0220")

    ##############################################################################80
    # Stage 3: The server should disclose a minimum amount of information about itself.
    #
    # Checks:
    #  * The "Server:" header shouldn't contain a version number or OS distribution code.
    #  * The server shouldn't be sending common nonstandard identifying headers (X-Powered-By)
    def get_header(self, headers, header_name):
        header_value = headers.get(header_name, "")
        self.log("INFO", f"Extracting {header_name}: {header_value}")
        return header_value

    def stage_3_server_information_disclosure(self, headers):
        self.log("INFO", "Stage 3: Information disclosure")

        server = self.get_header(headers, "Server")
        if server:
            if len(server.split()) <= 1:
                if "/" in server:
                    self.output(
                        "FAIL", TWA_CODES["TWA-0301"].format(server=server), "TWA-0301"
                    )
                else:
                    self.output(
                        "PASS",
                        f"Site sends 'Server', but probably only a vendor ID: {server}",
                    )
            else:
                self.output(
                    "FAIL", TWA_CODES["TWA-0302"].format(server=server), "TWA-0302"
                )
        else:
            self.output("PASS", "Site doesn't send 'Server' header")

        badheaders = ["X-Powered-By", "Via", "X-AspNet-Version", "X-AspNetMvc-Version"]
        for badheader in badheaders:
            content = self.get_header(headers, badheader)
            if content:
                self.output(
                    "FAIL",
                    TWA_CODES["TWA-0303"].format(badheader=badheader, content=content),
                    "TWA-0303",
                )
            else:
                self.output("PASS", f"Site doesn't send '{badheader}'")

    ##############################################################################80
    # Stage 4: The server shouldn't be serving SCM repositories, build tool files,
    # or common environment files.
    #
    # Checks:
    # * GET /.git/HEAD should 404.
    # * GET /.hg/store/00manifest.i should 404.
    # * GET /.svn/entries should 404.
    # * GET /.env should 404.
    # * GET /.envrc should 404.
    # * GET /.dockerenv should 404.
    def fetch_respcode(self, url):
        try:
            response = requests.head(
                url,
                allow_redirects=True,
                timeout=TWA_TIMEOUT,
                headers={"User-Agent": TWA_USER_AGENT},
            )
            return response.status_code, response.url
        except requests.RequestException as e:
            self.log("ERROR", f"Failed to fetch {url}: {e}")
            return None, None

    def stage_4_repo_and_env_disclosure(self):
        self.log("INFO", "Stage 4: SCM repo and env file disclosure")

        repo_files = [".git/HEAD", ".hg/store/00manifest.i", ".svn/entries"]
        for repo_file in repo_files:
            url = f"http://{self.domain}/{repo_file}"
            code, eurl = self.fetch_respcode(url)
            if code in [404, None] or repo_file not in eurl:
                self.output("PASS", f"No SCM repository at: {url}")
            elif code == 200:
                self.output("FAIL", TWA_CODES["TWA-0401"], "TWA-0401")
            elif code == 403:
                self.output("MEH", TWA_CODES["TWA-0402"], "TWA-0402")
            else:
                self.output(
                    "UNK",
                    f"Got a weird response code ({code}) when testing for SCM at: {url}",
                )

        env_files = [".env", ".envrc", ".dockerenv"]
        for env_file in env_files:
            url = f"http://{self.domain}/{env_file}"
            code, eurl = self.fetch_respcode(url)
            if code in [404, None] or env_file not in eurl:
                self.output("PASS", f"No environment file at: {url}")
            elif code == 200:
                self.output("FAIL", TWA_CODES["TWA-0403"], "TWA-0403")
            elif code == 403:
                self.output("MEH", TWA_CODES["TWA-0404"], "TWA-0404")
            else:
                self.output(
                    "UNK",
                    f"Got a weird response code ({code}) when testing for an environment file at: {url}",
                )

        config_files = [
            "config.xml",
            "config.json",
            "config.yaml",
            "config.ini",
            "config.cfg",
        ]
        for config_file in config_files:
            url = f"http://{self.domain}/{config_file}"
            code, eurl = self.fetch_respcode(url)
            if code in [404, None] or config_file not in eurl:
                self.output("PASS", f"No config file at: {url}")
            elif code == 200:
                self.output("FAIL", TWA_CODES["TWA-0405"], "TWA-0405")
            elif code == 403:
                self.output("MEH", TWA_CODES["TWA-0406"], "TWA-0406")
            else:
                self.output(
                    "UNK",
                    f"Got a weird response code ({code}) when testing for a config file at: {url}",
                )

        pm_files = [
            ".npmrc",
            "package.json",
            "package-lock.json",
            ".gem/credentials",
            "Gemfile",
            "Gemfile.lock",
            "Rakefile",
            ".pypirc",
            "setup.py",
            "setup.cfg",
            "requirements.txt",
            "Pipfile",
            "Pipfile.lock",
            "pyproject.toml",
            "Cargo.lock",
            "Cargo.toml",
        ]
        for pm_file in pm_files:
            url = f"http://{self.domain}/{pm_file}"
            code, eurl = self.fetch_respcode(url)
            if code in [404, None] or pm_file not in eurl:
                self.output("PASS", f"No package management file at: {url}")
            elif code == 200:
                self.output("FAIL", TWA_CODES["TWA-0407"], "TWA-0407")
            elif code == 403:
                self.output("MEH", TWA_CODES["TWA-0408"], "TWA-0408")
            else:
                self.output(
                    "UNK",
                    f"Got a weird response code ({code}) when testing for a package management file at: {url}",
                )

        build_files = [
            "Dockerfile",
            "docker-compose.yml",
            "Makefile",
            "GNUMakefile",
            "CMakeLists.txt",
            "configure",
            "configure.ac",
            "Makefile.am",
            "Makefile.in",
            "Justfile",
        ]
        for build_file in build_files:
            url = f"http://{self.domain}/{build_file}"
            code, eurl = self.fetch_respcode(url)
            if code in [404, None] or build_file not in eurl:
                self.output("PASS", f"No build file at: {url}")
            elif code == 200:
                self.output("FAIL", TWA_CODES["TWA-0409"], "TWA-0409")
            elif code == 403:
                self.output("MEH", TWA_CODES["TWA-0410"], "TWA-0410")
            else:
                self.output(
                    "UNK",
                    f"Got a weird response code ({code}) when testing for a build file at: {url}",
                )

    ##############################################################################80
    # Stage 5: Check if the server provides a robots.txt file.
    #
    # Check for "The Robots Exclusion Protocol".
    # Will follow redirects to ensure file exists.
    def stage_5_robots_and_security_check(self):
        self.log("INFO", "Stage 5: robots.txt and security.txt checks")

        url = f"http://{self.domain}/robots.txt"
        code, _ = self.fetch_respcode(url)

        if code == 200:
            self.output("PASS", "Site provides robots.txt")
            robots = self.fetch(url).text

            if "admin" in robots:
                self.output("MEH", TWA_CODES["TWA-0502"], "TWA-0502")

            if "cgi-bin" in robots:
                self.output("MEH", TWA_CODES["TWA-0503"], "TWA-0503")
        elif code == 404:
            self.output("MEH", TWA_CODES["TWA-0501"], "TWA-0501")
        else:
            self.output(
                "UNK",
                f"Got a weird response code ({code}) when testing for robots.txt at: {url}",
            )

        url = f"http://{self.domain}/.well-known/security.txt"
        code, _ = self.fetch_respcode(url)

        if code == 200:
            self.output("PASS", "Site provides security.txt")
            # TODO: Maybe test the contents of security.txt
        elif code == 404:
            self.output("MEH", TWA_CODES["TWA-0504"], "TWA-0504")
        else:
            self.output(
                "UNK",
                f"Got a weird response code ({code}) when testing for security.txt at: {url}",
            )

    ##############################################################################80
    # Stage 6: Check for CAA records.
    #
    # Checks:
    # * The domain should specify at least one issue record.
    # * The domain should specify at least one iodef record.
    def dig_caa_records(self, domain):
        try:
            result = subprocess.run(
                ["dig", "+noall", "+answer", "caa", domain],
                capture_output=True,
                text=True,
                timeout=TWA_TIMEOUT,
            )
            return result.stdout.strip().splitlines()
        except subprocess.CalledProcessError as e:
            self.log("ERROR", f"Failed to dig CAA records for {domain}: {e}")
            return []

    def stage_6_caa(self):
        self.log("INFO", "Stage 6: CAA checks")

        issuers = []
        wildcard_issuers = []
        iodefs = []
        valid = ""
        subdom = self.domain

        while "." in subdom and not valid:
            self.log("INFO", f"Checking {subdom}")
            records = self.dig_caa_records(subdom)

            if records:
                for record in records:
                    parts = record.split()
                    if len(parts) < 7:
                        continue
                    type_, flag, tag, value = (
                        parts[3],
                        parts[4],
                        parts[5],
                        parts[6].strip('"'),
                    )

                    if type_ == "CAA":
                        if flag and tag and value:
                            if int(flag) == 0:
                                if tag == "issue":
                                    if value:
                                        issuers.append(value)
                                        valid += "Y"
                                    else:
                                        self.output(
                                            "UNK", "Missing value for issue tag?"
                                        )
                                elif tag == "issuewild":
                                    if value:
                                        wildcard_issuers.append(value)
                                        valid += "Y"
                                    else:
                                        self.output(
                                            "UNK", "Missing value for issuewild tag?"
                                        )
                                elif tag == "iodef":
                                    if value:
                                        iodefs.append(value)
                                        valid += "Y"
                                    else:
                                        self.output(
                                            "UNK", "Missing value for iodef tag?"
                                        )
                                else:
                                    self.output(
                                        "UNK", f"Weird (nonstandard?) CAA tag: {tag}"
                                    )
                            else:
                                self.output(
                                    "UNK",
                                    f"Nonzero CAA flags: {flag} for {tag} {value}",
                                )
                        else:
                            self.output(
                                "UNK",
                                f"Malformed CAA record? (flag={flag}, tag={tag}, value={value})",
                            )

            subdom = ".".join(subdom.split(".")[1:])

        if not valid:
            self.output("FAIL", TWA_CODES["TWA-0601"], "TWA-0601")
            return

        if not issuers:
            self.output("FAIL", TWA_CODES["TWA-0602"], "TWA-0602")
        elif len(issuers) == 1 and issuers[0] == ";":
            self.output("FAIL", TWA_CODES["TWA-0603"], "TWA-0603")
        else:
            self.output(
                "PASS",
                f"Domain explicitly allows one or more issuers: {', '.join(issuers)}",
            )

        if not iodefs:
            self.output("MEH", TWA_CODES["TWA-0604"], "TWA-0604")
        else:
            self.output(
                "PASS",
                f"Domain specifies one or more reporting endpoints: {', '.join(iodefs)}",
            )

    ##############################################################################80
    # Stage 7: Check for common open development/backend ports.
    #
    # Checks:
    #  * Each port should not respond to a connection request.
    def stage_7_open_development_ports(self):
        self.log("INFO", "Stage 7: Check for common open development/backend ports")

        dev_ports = {
            1433: "Microsoft SQL Server default port",
            3000: "node.js (express.js), ruby on rails",
            3050: "Interbase, Firebird default port",
            3306: "MySQL and MariaDB default port",
            4443: "common https development port",
            4567: "sinatra default port",
            5000: "Flask and Kestrel default port",
            5432: "PostgreSQL default port",
            6379: "Redis default port",
            8000: "common http development port",
            8008: "common http development port",
            8080: "common http development port",
            8081: "common http development port",
            8086: "InfluxDB HTTP service default port",
            8088: "common http development port",
            8093: "Couchbase Query service REST traffic",
            8443: "common https development port",
            8888: "common http development port",
            9200: "Elasticsearch REST API default port",
            9292: "rack default port",
            27017: "MongoDB default port",
            33060: "MySQL X-Protocol default port",
        }

        if self.disableportscan:
            return

        threads = []
        for dev_port, dev_port_comment in dev_ports.items():
            thread = threading.Thread(
                target=self.probe_port, args=(dev_port, dev_port_comment)
            )
            threads.append(thread)
            thread.start()
            time.sleep(0.5)

        for thread in threads:
            thread.join()

    def probe_port(self, dev_port, dev_port_comment):
        if self.probe(dev_port):
            self.output(
                "FAIL",
                TWA_CODES["TWA-0701"].format(
                    dev_port=dev_port, dev_port_comment=dev_port_comment
                ),
                "TWA-0701",
            )
        else:
            self.output(
                "PASS",
                f"Domain is not listening on port {dev_port} ({dev_port_comment})",
            )

    ##############################################################################80
    # Stage 8: Cookie checks.
    #
    # Checks:
    #  * all cookies must have the secure flag.
    #  * each cookie should have the httponly flag. one MEH for each cookie that doesn't.
    def get_cookies(self, headers):
        cookies = headers.get("Set-Cookie", "")
        self.log("INFO", f"Extracting cookies: {cookies}")
        return cookies.split(", ") if cookies else []

    def get_field(self, cookie, field):
        field_pattern = re.compile(rf"{field}=(.*?);", re.IGNORECASE)
        match = field_pattern.search(cookie)
        return match.group(1) if match else ""

    def stage_8_cookie_checks(self):
        self.log("INFO", "Stage 8: Cookie checks")

        headers = self.fetch(f"https://{self.domain}", headers_only=True).headers
        cookies = headers.get("Set-Cookie", "").split(", ")

        if cookies:
            for cookie in cookies:
                cookie_name = cookie.split("=")[0]
                has_secure = "secure" in cookie.lower()
                has_httponly = "httponly" in cookie.lower()
                has_samesite = self.get_field(cookie, "SameSite")

                if has_secure and has_httponly:
                    self.output(
                        "PASS",
                        f"cookie '{cookie_name}' has both 'secure' and 'httponly' flags",
                    )
                elif has_secure and not has_httponly:
                    self.output("MEH", TWA_CODES["TWA-0801"], "TWA-0801")
                else:
                    self.output("FAIL", TWA_CODES["TWA-0802"], "TWA-0802")

                if has_samesite:
                    samesite_value = has_samesite.lower()
                    if samesite_value == "strict":
                        self.output(
                            "PASS",
                            f"cookie '{cookie_name}' has 'strict' SameSite flag set",
                        )
                    elif samesite_value == "lax":
                        self.output("MEH", TWA_CODES["TWA-0803"], "TWA-0803")
                    else:
                        self.output("FAIL", TWA_CODES["TWA-0804"], "TWA-0804")
                else:
                    self.output("MEH", TWA_CODES["TWA-0805"], "TWA-0805")

                has_secure_prefix = "__secure-" in cookie.lower()
                has_domain = self.get_field(cookie, "domain")

                if has_secure_prefix:
                    if has_secure:
                        if has_domain:
                            domain_value = has_domain.lower()
                            if domain_value == self.domain:
                                self.output(
                                    "PASS",
                                    f"cookie '{cookie_name}' passes all '__Secure' prefix checks",
                                )
                            else:
                                self.output("FAIL", TWA_CODES["TWA-0809"], "TWA-0809")
                        else:
                            self.output("FAIL", TWA_CODES["TWA-0806"], "TWA-0806")
                    else:
                        self.output("FAIL", TWA_CODES["TWA-0802"], "TWA-0802")

                has_host_prefix = "__host-" in cookie.lower()
                has_path = self.get_field(cookie, "path")

                if has_host_prefix:
                    if has_secure:
                        if not has_domain:
                            if has_path:
                                path_value = has_path.lower()
                                if path_value == "/":
                                    self.output(
                                        "PASS",
                                        f"cookie '{cookie_name}' passes all '__Host' prefix checks",
                                    )
                                else:
                                    self.output(
                                        "FAIL", TWA_CODES["TWA-0810"], "TWA-0810"
                                    )
                            else:
                                self.output("FAIL", TWA_CODES["TWA-0808"], "TWA-0808")
                        else:
                            self.output("FAIL", TWA_CODES["TWA-0807"], "TWA-0807")
                    else:
                        self.output("FAIL", TWA_CODES["TWA-0802"], "TWA-0802")

    ##############################################################################80
    # Run Stages
    ##############################################################################80
    def run(self):
        self.stage_0_has_https()
        self.stage_1_redirection()
        headers = self.fetch(f"https://{self.domain}", headers_only=True).headers
        self.stage_2_security_headers(headers)
        self.stage_3_server_information_disclosure(headers)
        self.stage_4_repo_and_env_disclosure()
        self.stage_5_robots_and_security_check()
        self.stage_6_caa()
        self.stage_7_open_development_ports()
        self.stage_8_cookie_checks()

        if self.score < 0:
            self.log("INFO", f"score {self.score} < 0, capping it at 0")
            self.score = 0

        print(
            f"{self.score} {self.npasses} {self.nmehs} {self.nfailures} {self.nunknowns} {self.nskips} {self.totally_screwed}"
        )

def main():
    parser = argparse.ArgumentParser(description="twa: a tiny website auditing script")
    parser.add_argument("domain", help="Domain to audit")
    parser.add_argument("-v", action="store_true", help="Enable verbose mode")
    parser.add_argument("-d", action="store_true", help="Disable port scan")
    parser.add_argument("-V", action="store_true", help="Show version and exit")

    args = parser.parse_args()

    if args.V:
        print(f"twa version {TWA_VERSION}")
        return

    auditor = TinyWebsiteAuditor(args.domain, args.v, args.d)
    auditor.run()


if __name__ == "__main__":
    main()
