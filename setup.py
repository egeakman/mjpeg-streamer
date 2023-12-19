from setuptools import find_packages, setup

__version__ = "2023.12.19"

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="od-mjpeg-streamer",
    author="Lapo Ciampi",
    author_email="84043476+lapociampi@users.noreply.github.com ",
    url="https://github.com/lapociampi/od-mjpeg-streamer",
    description="Simple MJPEG streamer for Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    version=__version__,
    license="AGPLv3",
    download_url=f"https://github.com/lapociampi/od-mjpeg-streamer/archive/{__version__}.tar.gz",
    packages=find_packages(where=".", exclude=["tests"]),
    python_requires=">=3.6",
    install_requires=[
        "setuptools",
        "numpy",
        "opencv-python",
        "aiohttp",
        "netifaces",
    ],
    keywords=[
        "aiohttp",
        "MJPEG",
        "asyncio",
        "OpenCV",
        "server",
        "multi-camera",
        "computer-vision",
        "streaming",
        "streamer",
        "video",
        "webcam",
        "ondemand"
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Topic :: Multimedia :: Video",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Security",
        "Framework :: AsyncIO",
        "Framework :: aiohttp",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
    ],
    project_urls={
        "Homepage": "https://github.com/lapociampi/od-mjpeg-streamer",
        "Issues": "https://github.com/lapociampi/od-mjpeg-streamer/issues",
    },
)
