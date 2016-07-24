#!/usr/bin/perl

use strict;
use warnings;

use URI::Escape;

my $prgname = $0;


#### find_setup_ini_file ###############################################
# Parse Cygwin's setup.rc file to find the last setup.ini file it used.

sub find_setup_ini_file {
	open my $rc, '<', '/etc/setup/setup.rc'
			or usage("could not read setup.rc file: $!");

	my ($path, $mirror);
	while (<$rc>) {
		chomp;

		if ($_ eq 'last-cache') {
			$path = <$rc>;
			chomp $path;
			$path =~ s/^\s+//;
			open my $cp, '-|', "cygpath -u '$path'";
			$path = <$cp>;
			chomp $path;
			close $cp;
		}
		elsif ($_ eq 'last-mirror') {
			$mirror = <$rc>;
			chomp $mirror;
			$mirror =~ s/^\s+//;
			$mirror = uri_escape($mirror);
		}
	}

	close $rc;

	usage("could not find last Cygwin cache dir") unless $path;
	usage("could not find last Cygwin DL mirror") unless $mirror;

	open my $uname, '-|', 'uname -m' or die "uname -m failed: $!\n";
	my $plat = <$uname>;
	chomp $plat;
	close $uname;

	$path .= "/$mirror/$plat/setup.ini";
	usage("could not find setup.ini") unless -r $path;
	return $path;
}


#### get_dependency_order ##############################################
# Return a hash mapping package names to their index on the "Dependency
# order" line written to /var/log/setup.log.full by setup.exe.  Lower
# numbers mean they're farther to the left and hence more depended-upon,
# so the index of "base-cygwin" is 0, "cygwin" is 1, etc.

sub get_dependency_order {
	open my $log, '<', '/var/log/setup.log.full'
			or usage("failed to read setup log: $!");
	my @lines = grep { /^Dependency order/ } <$log>;
	usage("no dependency order line in setup log") if @lines == 0;
	usage("multiple dependency order lines found") unless @lines == 1;
	
	my ($preamble, $deporder) = split ':', $lines[0];
	my @packages = split ' ', $deporder;

	my $i = 0;
	my %deps;
	for my $p (@packages) {
		$deps{$p} = $i++;
	}

	return \%deps;
}


#### get_installed_package_list ########################################
# Return a list of names of installed packages

sub get_installed_package_list {
	open my $db, '<', '/etc/setup/installed.db'
			or usage("failed to read installed package DB file: $!");

	my $header = <$db>;
	my @pkgnames;
	while (<$db>) {
		my ($name) = split;
		push @pkgnames, $name;
	}

	return \@pkgnames;
}


#### parse_cygwin_setup_ini_file #######################################
# Extract dependency info from the Cygwin setup.ini file.

sub parse_cygwin_setup_ini_file {
	my ($inifile, $piref) = @_;

	open my $ini, '<', $inifile
			or die "Cannot read INI file $inifile: $!\n";

	# Skip to first package entry
	while (<$ini>) { last if /^@/; }

	# Parse package entries
	my %deps;
	while (defined $_) {
		chomp;
		my $p = substr $_, 2;
		my $obs = 0;

		while (<$ini>) {
			if (/^@/) {
				# Found next package entry; restart outer loop
				last;
			}
			elsif (/^category: Base$/) {
				# Mark this one as a special sort of root package: one
				# we're going to install regardless of user selection,
				# so we need not list it in our output.
				$piref->{$p} = 2;
			}
			elsif (/^category: _obsolete$/) {
				# Select this package's replacement instead below.
				$piref->{$p} = 0;
				$obs = 1;
			}
			elsif (/^requires:/) {
				# Save this package's requirements as its dependents list.
				my ($junk, @deps) = split;
				$deps{$p} = \@deps;

				# If this package was marked obsolete above, select its
				# replacement as provisionally to-be-installed.  That
				# package still might end up removed from our output list
				# if it in turn is a dependent of one of the packages we 
				# consider a "root" package at the end.
				$piref->{$deps[0]} = 1 if $obs;
			}
		}
	}

	close $ini;
	return \%deps;
}


#### usage #############################################################
# Print usage message plus optional error string, then exit

sub usage {
	my ($error) = @_;
	print "ERROR: $error\n\n" if length($error);

	print <<"USAGE";
usage: $prgname

    Finds the last-used Cygwin setup.ini file, then uses the
    package dependency info found within it to pare the list of
    currently-installed Cygwin packages down to a "root" set,
    being those that will implicitly install all of the others
    as dependencies.
    
    The output is a list suitable for passing to setup.exe -P.
USAGE
	exit ($error ? 1 : 0);
}


#### main ##############################################################

my $inifile = find_setup_ini_file;

# Convert package list to a hash so we can mark them non-root by name
my $pkgnames = get_installed_package_list;
my %packages = map { $_ => 1 } @$pkgnames;

my $deps = parse_cygwin_setup_ini_file($inifile, \%packages);
my $deporder = get_dependency_order;

# For each installed package, mark all of its dependencies as non-root
# since those will be installed if the requiring package is installed.
for my $p (@$pkgnames) {
	my $pdref = $deps->{$p};
	for my $d (@$pdref) {
		# Package $p depends on $d, but only mark it as non-root if $p
		# was to the right of $d in the dependency order list written by
		# setup.exe on the last install.  Otherwise, setup.exe is saying
		# $p is more depended-upon than $d, which means we're looking at
		# a dependency graph cycle.  That means we always call the least
		# depended-upon package in that loop as the "root," but that
		# choice is not important.  What that matters is that we avoid
		# marking all packages in that loop as non-root, since then none
		# of them get installed.
		$packages{$d} = 0 if $deporder->{$p} > $deporder->{$d};
	}
}

# Collect list of root packages and print it out
print join ',', sort(grep { $packages{$_} == 1 } @$pkgnames);

