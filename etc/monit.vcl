# We provide a 'special' URL for monit to hit that will be entirely handled by
# Varnish and never touch a backend. This means that Monit will actually be able
# to test to see if Varnish is up, not if Varnish and Apache are up.

# Define the vcl_recv subroutine, ours will get handled first, then any others.
sub vcl_recv {
  # Change this URL to something that will NEVER be a real URL for the hosted
  # site, it will be effectively inaccessible.
  if (req.url == "/monit-check-url") {
    error 200 "Varnish up";
  }
}
