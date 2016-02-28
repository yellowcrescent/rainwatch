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
var shared_key = "";

/**
 * Utility functions
 **/

function rwAjax(route,data,$scope,$http,callback) {

	// add auth info to request headers
	rheaders = { 'WWW-Authenticate': shared_key };
	$scope.ajcb = callback;
	return $http.post(route, data, rheaders)
		.success(function(data, status, headers, config) {
			$scope.ajcb(data);
			return true;
		})
		.error(function(data, status, headers, config) {
			console.log("Error retrieving JSON data from server via AJAX request");
			return false;
		});

}

/**
 * Controllers
 **/

function homeController($scope, $location, $http) {

	// get info
	rwAjax('/api/info', {}, $scope, $http, function(rwinfo) {
		$scope.rwinfo = rwinfo;
	});

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
			.otherwise({
				redirectTo: '/'
			});
	});
