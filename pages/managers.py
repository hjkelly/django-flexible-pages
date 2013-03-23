import logging

from django.core.cache import cache
from django.db import models

from . import validators


log = logging.getLogger('pages.cache')


class PageManager(models.Manager):
    # This is what we'll put in the cache, to mark a non-existent page.
    CACHE_404_VALUE = -1
    CACHE_TIMEOUT = 2*60

    def get_from_db(self, path, path_key):
        """
        Hit the database, cache the result, and return/raise when done.
        """
        # This is our actual query!
        try:
            page = self.get_query_set().filter(url=path)[:1][0]
        # If it's not in the DB, update the cache with that.
        except IndexError:
            cache.set(path_key, self.CACHE_404_VALUE, self.CACHE_TIMEOUT)
            log.debug("Set in cache: %s = %s",
                      path_key,
                      cache.get(path_key, 'not found in cache'))
            raise self.model.DoesNotExist("That path couldn't be found in the "
                                          "cache, nor in the database.")
        # If nothing went wrong, store the page in the cache.
        else:
            cache.set(path_key, page, self.CACHE_TIMEOUT)
            log.debug("Set in cache: %s = %s",
                      path_key,
                      cache.get(path_key, 'not found in cache'))
            return page

    def get_from_cache(self, path):
        """
        Hit the cache for a URL, and if it's not there, hit the database.
        """
        # This is the cache key for the given path - safer than putting the
        # path in directly.
        path_key = self.model.get_key_for_path(path)

        # Hit the cache!
        cache_value = cache.get(path_key, None)

        # If a 404 was cached, RAISE that.
        if cache_value == self.CACHE_404_VALUE:
            log.debug("The cache reported that path as a 404:    %s %s",
                      path.ljust(30),
                      path_key)
            raise self.model.DoesNotExist("That path was in the cache as a "
                                          "404.")

        # If a page was cached:
        if isinstance(cache_value, self.model):
            # Just to be safe, make sure the URL matches. If it does, RETURN.
            if cache_value.url == path:
                log.debug("Hit the cache and found the Page:         %s %s",
                          path.ljust(30),
                          path_key)
                return cache_value
            # If, somehow, this was a hash collision, report that mess. Then
            # hit the DB.
            else:
                log.error("Encountered a hash collision in the keys for "
                          "pages. We were looking for a page whose path "
                          "is {request_path}, but the cache returned one "
                          "whose path (url field) is {cache_value_path}. "
                          "If this is indeed the case, you should update "
                          "the caching algorithm somehow to fix the "
                          "collision, or you should prevent caching "
                          "of keys known to have collisions (to avoid "
                          "thrashing).", {'request_path': path,
                          'cache_value_path': cache_value.url})

        # If it wasn't cached, hit the DB (caching it as well), and return the
        # result. Let any errors be raised: they should be handled higher up.
        try:
            db_value = self.get_from_db(path, path_key)
        except self.model.DoesNotExist as e:
            log.debug("Hit the database, and didn't find a Page: %s %s",
                      path.ljust(30),
                      path_key)
            raise e
        else:
            log.debug("Hit the database, but found the Page:     %s %s",
                      path.ljust(30),
                      path_key)
            return db_value

    def get_for_url(self, path):
        """
        Validate a path, then go through the cache to get it.
        """
        # Could this even be stored in the DB?
        if not validators.is_root_relative_url(path):
            raise self.model.DoesNotExist("That URL almost surely doesn't "
                                          "exist, because our system wouldn't "
                                          "allow one of that format.")

        # If so, hit the cache! Let any exceptions rise up for their callers
        # to handle.
        return self.get_from_cache(path)

