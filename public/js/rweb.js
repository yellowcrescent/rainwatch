/**
 ******************************************************************************
 **vim: set ts=4 sw=4 noexpandtab syntax=javascript:
 *
 * rainwatch: rweb.js
 * Client-side logic for web management interface
 *
 * Copyright (c) 2016 Jacob Hipps - jacob@ycnrg.org
 * https://ycnrg.org/
 *
 * @author		Jacob Hipps - jacob@ycnrg.org
 *
 *****************************************************************************/

/**
 * Angular config & globals
 **/

var rainwatch = angular.module('rainwatch', ['ngRoute', 'ngAnimate', 'mgcrea.ngStrap', 'cgBusy']);

// Shared key for authentication
var shared_key = "6048a740cacc5cc11b3192b6815136fc";

// set defaults & other initialization
rainwatch.run(function($http) {
	$http.defaults.headers.common = { 'WWW-Authenticate': shared_key };
});

/**
 * Utility functions
 **/

function rwAjax(route,data,$scope,$http,callback) {

	$scope.ajcb = callback;
	return $http.post(route, data)
		.success(function(data, status, headers, config) {
			if(typeof data.status == 'undefined') {
				// return raw object
				$scope.ajcb(data);
			} else {
				// pull data from 'result' and check status
				$scope.lastStatus = data.status;
				$scope.ajcb(data.result);
			}
			return true;
		})
		.error(function(data, status, headers, config) {
			console.log("Error retrieving JSON data from server via AJAX request");
			return false;
		});

}

function mkArray(indict) {
	var outarray = [];
	for(kk in indict) {
		var tobj = indict[kk];
		tobj['_id'] = kk;
		outarray.push(tobj);
	}
	return outarray;
}

function parse_dates(inarr,keyname) {
	var monlist = [ "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" ];
	for(kk in inarr) {
		var txd = new Date(inarr[kk][keyname] * 1000);
		//inarr[kk]['date_string'] = txd.getDay() + ' ' + monlist[txd.getMonth() - 1] + ' ' +txd.getFullYear() + ' ' + txd.getHours() + ':' + txd.getMinutes() + ':' + txd.getSeconds();
		inarr[kk]['date_string'] = txd.toDateString();
		inarr[kk]['time_string'] = txd.toTimeString().replace(/ GMT[^ ]* /i,' ');
	}

	return inarr;
}

/**
 * Controllers
 **/

function homeController($scope, $location, $http) {

	// set up refresh function
	window.refresh = function() {
		// make spinny thing spin
		document.getElementById('freshspin').classList.add('fa-spin');
		// get info
		rwAjax('/api/info', {}, $scope, $http, function(rwinfo) {
			$scope.rwinfo = rwinfo;
			document.getElementById('freshspin').classList.remove('fa-spin');
		});
	};

	// perform initial load
	window.refresh();

}

function torlistController($scope, $filter, $location, $http) {

	// create orderBy filter & set defaults
	var orderBy = $filter('orderBy');
	$scope.sort_pred = 'time_added';
	$scope.sort_rev = true;

	// set up refresh function
	window.refresh = function() {
		// make spinny thing spin
		document.getElementById('freshspin').classList.add('fa-spin');
		// retrieve torrent list
		rwAjax('/api/torrent/list', {}, $scope, $http, function(dresp) {
			// apply ordering & update list
			$scope.torlist = orderBy(parse_dates(mkArray(dresp),'time_added'), $scope.sort_pred, $scope.sort_rev);
			document.getElementById('freshspin').classList.remove('fa-spin');
		});
	};

	// perform initial load
	window.refresh();
}

/**
 * Routing configuration
 **/

rainwatch.config(
	function($routeProvider, $locationProvider) {
		//$locationProvider.html5Mode(true);

		$routeProvider
			.when('/', {
				templateUrl: '/routes/home.html',
				controller: homeController
			})
			.when('/torrents', {
				templateUrl: '/routes/torrents.html',
				controller: torlistController
			})
			.otherwise({
				redirectTo: '/'
			});
	});
