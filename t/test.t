#
#   prove -v t/test.t [ :: [--verbose] [--dry_run] ]
#
# Assumes containers are built and running (use up.sh)
#
# Dependencies:
#   jq
# To install:
#   cpan App::cpanminus
#   # restart shell, then get the dependencies:
#   cpanm --installdeps .
# For more details:
#   http://www.cpan.org/modules/INSTALL.html

use 5.16.3;
use strict;
use warnings;

use Getopt::Long qw(GetOptions);

use Test::More tests => 1;
use Test::File::Contents;

use lib './t';
use Support;

our $verbose = 0;
our $dry_run = 0;

our $SUBMITTER_ID='test@email.com';

# read the .env file
use Dotenv;      
Dotenv->load;

our $HOST_PATH = "http://localhost:$ENV{'API_PORT'}"; #8086;

GetOptions('dry_run' => \$dry_run,
	   'verbose' => \$verbose) or die "Usage: prove -v t/$0 [ :: [--verbose] ] \n";
if($verbose){
    print("+ dry_run: $dry_run\n");
    print("+ verbose: $verbose\n");
    print("+ API_PORT: $ENV{'API_PORT'}\n");
}

my $fn ;

cleanup_out();

$fn = "test-1.json";
generalize_output($fn, cmd("POST", rawf($fn), "submit?submitter_id=${SUBMITTER_ID}&number_of_components=2", "-F 'gene_expression=@./t/input/expression.csv;type=application/vnd.ms-excel' -H 'Content-Type: multipart/form-data' -H 'accept: application/json'"), ["start_time", "end_time", "contents"]);
files_eq(f($fn), "t/out/${fn}",                                                    "Get PCA table");

