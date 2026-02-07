"""
FTP Access Tester for Fedresurs Archive.

Tests access to FTP server with demo credentials and checks availability
of recent archives (last 6 months).
"""
import ftplib
from datetime import datetime, timedelta
from typing import List, Dict, Any
import sys


class FTPAccessTester:
    """Tests FTP access to Fedresurs archive."""

    def __init__(self, host: str, user: str, password: str, download_limit_mb: int = 50):
        self.host = host
        self.user = user
        self.password = password
        self.download_limit_mb = download_limit_mb
        self.ftp = None

    def connect(self) -> bool:
        """
        Connect to FTP server.

        Returns:
            True if connection successful
        """
        try:
            print(f"🔌 Connecting to {self.host}...")
            self.ftp = ftplib.FTP(self.host, timeout=30)
            self.ftp.login(self.user, self.password)
            print(f"✅ Connected successfully as {self.user}")
            print(f"📁 Welcome message: {self.ftp.getwelcome()}")
            return True
        except ftplib.error_perm as e:
            print(f"❌ Authentication failed: {e}")
            return False
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    def list_directory(self, path: str = "/") -> List[str]:
        """
        List files in directory.

        Args:
            path: Directory path

        Returns:
            List of files
        """
        try:
            self.ftp.cwd(path)
            files = self.ftp.nlst()
            return files
        except Exception as e:
            print(f"❌ Failed to list directory {path}: {e}")
            return []

    def get_file_size(self, filename: str) -> int:
        """
        Get file size in bytes.

        Args:
            filename: File name

        Returns:
            File size in bytes, or 0 if error
        """
        try:
            return self.ftp.size(filename)
        except Exception as e:
            print(f"⚠️  Could not get size for {filename}: {e}")
            return 0

    def check_recent_archives(self, months: int = 6) -> List[Dict[str, Any]]:
        """
        Check for archives from last N months.

        Args:
            months: Number of months to check

        Returns:
            List of archive info dicts
        """
        archives = []
        today = datetime.now()

        print(f"\n📦 Checking archives for last {months} months...")

        for i in range(months):
            # Calculate target month
            target_date = today - timedelta(days=30 * i)
            year = target_date.year
            month = target_date.month

            # Common archive naming patterns
            patterns = [
                f"fz127_{year}{month:02d}.zip",
                f"fedresurs_{year}_{month:02d}.zip",
                f"messages_{year}{month:02d}.tar.gz",
                f"{year}/{month:02d}/archive.zip",
            ]

            for pattern in patterns:
                if self._check_file_exists(pattern):
                    size_bytes = self.get_file_size(pattern)
                    size_mb = size_bytes / (1024 * 1024)

                    archives.append({
                        "filename": pattern,
                        "year": year,
                        "month": month,
                        "size_bytes": size_bytes,
                        "size_mb": round(size_mb, 2),
                        "accessible": size_mb < self.download_limit_mb
                    })

                    print(f"  ✅ Found: {pattern} ({size_mb:.2f} MB)")
                    break

        return archives

    def _check_file_exists(self, filename: str) -> bool:
        """Check if file exists on FTP server."""
        try:
            # Try to get size (will fail if file doesn't exist)
            self.ftp.size(filename)
            return True
        except:
            return False

    def test_download(self, filename: str, max_bytes: int = 1024) -> bool:
        """
        Test download by fetching first N bytes.

        Args:
            filename: File to test
            max_bytes: Max bytes to download

        Returns:
            True if download works
        """
        try:
            print(f"\n🧪 Testing download: {filename}")

            downloaded = bytearray()

            def callback(data):
                downloaded.extend(data)
                if len(downloaded) >= max_bytes:
                    raise ftplib.Error("Test limit reached")

            try:
                self.ftp.retrbinary(f"RETR {filename}", callback)
            except ftplib.Error as e:
                if "Test limit reached" in str(e):
                    pass  # Expected
                else:
                    raise

            print(f"  ✅ Downloaded {len(downloaded)} bytes successfully")
            return True

        except Exception as e:
            print(f"  ❌ Download test failed: {e}")
            return False

    def close(self):
        """Close FTP connection."""
        if self.ftp:
            try:
                self.ftp.quit()
                print("\n👋 Disconnected")
            except:
                pass

    def run_full_test(self) -> Dict[str, Any]:
        """
        Run complete FTP access test suite.

        Returns:
            Test results summary
        """
        results = {
            "connection": False,
            "root_files": [],
            "recent_archives": [],
            "download_test": False
        }

        # Test 1: Connection
        if not self.connect():
            return results

        results["connection"] = True

        # Test 2: List root directory
        print("\n📂 Listing root directory...")
        root_files = self.list_directory("/")
        results["root_files"] = root_files[:20]  # First 20 files
        print(f"  Found {len(root_files)} items")
        if root_files:
            print("  Sample files:")
            for f in root_files[:5]:
                print(f"    - {f}")

        # Test 3: Check recent archives
        archives = self.check_recent_archives(months=6)
        results["recent_archives"] = archives

        # Test 4: Download test (if archives found)
        if archives:
            # Try to download from first accessible archive
            accessible = [a for a in archives if a["accessible"]]
            if accessible:
                test_file = accessible[0]["filename"]
                results["download_test"] = self.test_download(test_file, max_bytes=10240)
            else:
                print("\n⚠️  No archives under download limit, skipping download test")

        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"  Connection: {'✅ SUCCESS' if results['connection'] else '❌ FAILED'}")
        print(f"  Root access: {'✅ SUCCESS' if results['root_files'] else '❌ FAILED'}")
        print(f"  Archives found: {len(results['recent_archives'])}")
        print(f"  Download test: {'✅ SUCCESS' if results['download_test'] else '❌ FAILED'}")

        if results["recent_archives"]:
            accessible_count = sum(1 for a in results["recent_archives"] if a["accessible"])
            print(f"  Accessible archives (<{self.download_limit_mb}MB): {accessible_count}")

        return results


def main():
    """Run FTP access test with demo credentials."""
    print("=" * 60)
    print("🔬 Fedresurs FTP Access Test")
    print("=" * 60)

    # Demo credentials (update with actual values)
    tester = FTPAccessTester(
        host="ftp.fedresurs.ru",
        user="demo",
        password="demo",
        download_limit_mb=50
    )

    try:
        results = tester.run_full_test()

        # Exit code based on results
        if results["connection"] and results["recent_archives"]:
            print("\n🎉 FTP access is WORKING! Ready for integration.")
            sys.exit(0)
        elif results["connection"]:
            print("\n⚠️  FTP connection works but no archives found.")
            sys.exit(1)
        else:
            print("\n❌ FTP access FAILED. Check credentials or network.")
            sys.exit(2)

    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(3)
    finally:
        tester.close()


if __name__ == "__main__":
    main()
