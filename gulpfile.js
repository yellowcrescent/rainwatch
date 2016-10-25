/**
 ******************************************************************************
 **%%vim: set ts=4 sw=4 expandtab syntax=javascript:
 *
 * gulpfile.js
 * Rainwatch > Gulpfile for task running
 *
 * Copyright (c) 2016 J. Hipps / Neo-Retro Group
 * https://ycnrg.org/
 *
 * @author      Jacob Hipps - jacob@ycnrg.org
 * @repo        https://git.ycnrg.org/projects/YRW/repos/rainwatch
 *
 *****************************************************************************/

var pkgdata = require('./package');
var gulp = require('gulp');
var compass = require('gulp-compass');
var gutil = require('gulp-util');
var bower = require('gulp-bower');
var jshint = require('gulp-jshint');
var run = require('gulp-run');
var jshintBamboo = require('gulp-jshint-bamboo');
var jshintSummary = require('jshint-stylish-summary');
var S = require('string');
var spawn = require('child_process').spawnSync;
var C = gutil.colors;
var basedir = process.cwd();

function pylintParser(indata, showTypes) {
    var results = { error: 0, warning: 0, refactor: 0, convention: 0 };
    var inlines = indata.toString().split('\n');
    var lpadding = 40;
    var lpaddingMin = 4;

    for(lnum in inlines) {
        var tline = inlines[lnum];
        if(tline[0] == ' ' || tline[0] == '*') continue;
        var toks = tline.match(/^([^:]+):([0-9]+): \[([A-Z0-9]+)\(([^\)]+)\), (?:([^ ]+) )?\] (.+)$/);
        if(!toks) continue;
        if(toks[3][0] == 'E') {
            results['error']++;
            var colorized_msg = C.red(toks[3] + ": " + toks[6] + " <" + toks[4] + ">")
        } else if(toks[3][0] == 'W') {
            results['warning']++;
            var colorized_msg = C.yellow(toks[3] + ": " + toks[6] + " <" + toks[4] + ">")
        } else if(toks[3][0] == 'R') {
            results['refactor']++;
            var colorized_msg = C.cyan(toks[3] + ": " + toks[6] + " <" + toks[4] + ">")
        } else if(toks[3][0] == 'C') {
            results['convention']++;
            var colorized_msg = C.gray(toks[3] + ": " + toks[6] + " <" + toks[4] + ">")
        }

        if(showTypes.search(toks[3][0]) >= 0) {
            var lpad = lpadding - (toks[1] + ':' + toks[2]).length;
            if(lpad < lpaddingMin) lpad = lpaddingMin;
            console.log("    " + C.white(toks[1]) + ":" + C.white(toks[2]) + S('').pad(lpad).s + colorized_msg);
        }
    }
    return results;
}

// compass task:
// compile scss files to css
gulp.task('compass', function() {
    return gulp.src('public/sass/*.scss')
            .pipe(compass({
                config_file: 'config.rb',
                css: 'public/css',
                image: 'public/img',
                sass: 'public/sass'
            }))
            .on('error', function(err) {
                gutil.log(C.red("Compass build failed: " + err));
            });
});

gulp.task('bower', function() {
    return bower({ cmd: 'install' });
});

// Python linting task
var pysource = [ 'rwatch' ];
var pylintrc = '.pylintrc';
var pylintTypes = 'EW';
var PYERR = { FATAL: 1, ERROR: 2, WARNING: 4, REFACTOR: 8, CONVENTION: 16, USAGE: 32 };

gulp.task('pylint', function() {
    gutil.log("Running pylint with config file " + C.white(pylintrc));
    var sout = spawn('pylint3', [ '--rcfile=' + pylintrc ].concat(pysource));
    if(sout.status & PYERR.USAGE) {
        gutil.log(C.red("pylint reported usage error. Please check gulp config and file locations."))
        throw new Error("pylint failed (" + sout.status + ")");
    } else if(sout.status & PYERR.FATAL) {
        gutil.log(C.red("*** pylint reported fatal error ***"));
    }
    //gutil.log("sout =", sout);
    var results = pylintParser(sout.stdout, pylintTypes);
    gutil.log("Linting complete: %d errors, %d warnings, %d refactor, %d convention",
              results['error'], results['warning'], results['refactor'], results['convention']);
});

// Javascript linting task
var jsource = [ 'public/js/*.js' ];
var jreporter = 'jshint-stylish';

gulp.task('jslint', function() {
    return gulp.src(jsource, { base: './' })
            .pipe(jshint('.jshintrc'))
            .pipe(jshint.reporter(jreporter))
            .pipe(jshintSummary.collect())
            .pipe(jshint.reporter('fail'))
            .on('end', jshintSummary.summarize());
});

// default task
gulp.task('default', [ 'jslint', 'pylint', 'bower', 'compass' ]);
gulp.task('lint', [ 'jslint', 'pylint' ]);
