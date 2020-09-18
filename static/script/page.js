(function (window) {
	// Current instructions shown
	var pShown;
	var site;
	var knownVers = ['85', '81', '75', '70', '62', '50', '47', '46', '45', '36', '22', '10']
	
	function main() {
		
		switch (pathname) {
			case '/downloads':
				site = 'downloads';
				break;
			default:
				site = 'whateverdontcare';
		}
		
		pShown = null;
		
		if (site == 'downloads') {
			setInterval(function () {
				if (window.pageYOffset > 10) {
					window.scrollTo(0, document.body.scrollHeight);
				} else {
					window.scrollTo(0, 0);
				}
			}, 500);
		}
	}
	
	function getJson(file) {
		var req = new XMLHttpRequest();
		req.open('GET', '/static/'+file+'.json', false);
		req.send();
		if (req.status == 200) {
			if (req.response != undefined) {
				return JSON.parse(req.response);
			}
		}
	}
	
	function isMirrored(s, m) {
		for (var i in m) {
			if (m[i] == s) return true;
		}
		return false;
	}
	
	function getDownloads(lang) {
		var gP = 'http://storage.googleapis.com/escargot-storage-1/public/';
		var eP = 'http://storage.log1p.xyz/';
		
		var d = getJson('json/downloads');
		var m = getJson('json/mirrored');
		
		for (var i in d.lang) {
			// This resets the href to avoid a link to a previously selected from being stored
			document.getElementById('up-'+i).href = '#';
			document.getElementById('pp-'+i).href = '#';
		}
		
		max_pp = null;
		
		c = 0;
		
		vers = Object.keys(d[lang]);
		//sort versions by descending
		vers.sort(function(a, b){return b - a});
		
		//prepatched
		for (var i = 0; i < vers.length; i++) {
			ver = vers[i];
			
			bp = d[lang][ver][0];
			if (bp == '' || bp == null) continue;
			if (c == 0) max_pp = ver;
			var t = 'patched-installer/' + bp;
			var a = document.getElementById('pp-'+ver);
			if (isMirrored(t, m)) {
				a.href = eP + t;
			} else {
				a.href = gP + t;
			}
			
			c++;
		}
		
		//unpatched
		for (var i = 0; i < vers.length; i++) {
			ver = vers[i];
			
			bu = d[lang][ver][1];
			if (bu == '' || bu == null) continue;
			var t = 'msn-installer/' + bu;
			var a = document.getElementById('up-'+ver);
			if (isMirrored(t, m)) {
				a.href = eP + t;
			} else {
				a.href = gP + t;
			}
		}
		
		if (max_pp == null) {
			document.getElementById('recommended').style.display = 'none';
		} else {
			document.getElementById('reco-ver').innerHTML = versionToString(max_pp);
			document.getElementById('recommended').href = document.getElementById('pp-' + max_pp).href;
		}
		
		for (var i = 0; i < knownVers.length; i++) {
			ver = knownVers[i];
			
			var x = document.getElementById('up-'+ver);
			if (x.href.indexOf('#') != -1) {
				x.style.display = 'none';
			} else {
				x.style.display = 'inline-block';
			}
			
			var x = document.getElementById('pp-'+ver);
			if (x.href.indexOf('#') != -1) {
				x.style.display = 'none';
			} else {
				x.style.display = 'inline-block';
			}
		}
	}
	
	function versionToString(ver) {
		switch (ver.toString()) {
			case '09':
				return 'WLM 09';
			case '85':
				return 'WLM 8.5';

		}
		
		return 'undefined';
	}
	
	function showPatchingInstructions(ver) {
		if (pShown == ver) return;
		hideP(pShown);
		pShown = ver;
		document.getElementById('patch'+ver).style.display = 'block';
	}
	
	function hideP(ver) {
		if (ver == null) return;
		document.getElementById('patch'+ver).style.display = 'none';
	}
	
	function waitForDomLoaded(f) {
		if (document.addEventListener) {
			document.addEventListener('DOMContentLoaded', f);
		} else {
			setTimeout(f, 9);
		}
	}
	
	window.getDownloads = getDownloads;
	window.showPatchingInstructions = showPatchingInstructions;
	waitForDomLoaded(main);
})(window);
