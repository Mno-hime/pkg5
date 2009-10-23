#!/usr/bin/python2.4
#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#

#
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

import os
import urlparse

# EmptyI for argument defaults; can't import from misc due to circular
# dependency.
EmptyI = tuple()

class ApiException(Exception):
        pass

class ImageNotFoundException(ApiException):
        """Used when an image was not found"""
        def __init__(self, user_specified, user_dir, root_dir):
                ApiException.__init__(self)
                self.user_specified = user_specified
                self.user_dir = user_dir
                self.root_dir = root_dir

class VersionException(ApiException):
        def __init__(self, expected_version, received_version):
                ApiException.__init__(self)
                self.expected_version = expected_version
                self.received_version = received_version

class PlanExistsException(ApiException):
        def __init__(self, plan_type):
                ApiException.__init__(self)
                self.plan_type = plan_type

class ActuatorException(ApiException):
        def __init__(self, e):
                ApiException.__init__(self)
                self.exception = e

        def __str__(self):
                return str(self.exception)

class PrematureExecutionException(ApiException):
        pass

class AlreadyPreparedException(ApiException):
        pass

class AlreadyExecutedException(ApiException):
        pass

class ImageplanStateException(ApiException):
        def __init__(self, state):
                ApiException.__init__(self)
                self.state = state


class ImagePkgStateError(ApiException):

        def __init__(self, fmri, states):
                ApiException.__init__(self)
                self.fmri = fmri
                self.states = states

        def __str__(self):
                return _("Invalid package state change attempted '%(states)s' "
                    "for package '%(fmri)s'.") % { "states": self.states,
                    "fmri": self.fmri }


class IpkgOutOfDateException(ApiException):
        pass

class ImageUpdateOnLiveImageException(ApiException):
        pass

class RebootNeededOnLiveImageException(ApiException):
        pass

class CanceledException(ApiException):
        pass

class PlanMissingException(ApiException):
        pass

class NoPackagesInstalledException(ApiException):
        pass

class PermissionsException(ApiException):
        def __init__(self, path):
                ApiException.__init__(self)
                self.path = path

        def __str__(self):
                if self.path:
                        return _("Could not operate on %s\nbecause of "
                            "insufficient permissions. Please try the command "
                            "again using pfexec\nor otherwise increase your "
                            "privileges.") % self.path
                else:
                        return _("""
Could not complete the operation because of insufficient permissions. Please
try the command again using pfexec or otherwise increase your privileges.
""")

class FileInUseException(PermissionsException):
        def __init__(self, path):
                PermissionsException.__init__(self, path)
                assert path

        def __str__(self):
                return _("Could not operate on %s\nbecause the file is "
                    "in use. Please stop using the file and try the\n"
                    "operation again.") % self.path


class ReadOnlyFileSystemException(PermissionsException):
        """Used to indicate that the operation was attempted on a 
        read-only filesystem"""

        def __init__(self, path):
                ApiException.__init__(self)
                self.path = path

        def __str__(self):
                if self.path:
                        return _("Could not complete the operation on %s: "
                            "read-only filesystem\n") % self.path
                return _("Could not complete the operation: read-only "
                        "filesystem.")


class PlanCreationException(ApiException):
        def __init__(self, unmatched_fmris=EmptyI, multiple_matches=EmptyI,
            missing_matches=EmptyI, illegal=EmptyI,
            constraint_violations=EmptyI, badarch=EmptyI, not_installed=EmptyI,
            installed=EmptyI):
                ApiException.__init__(self)
                self.unmatched_fmris = unmatched_fmris
                self.multiple_matches = multiple_matches
                self.missing_matches = missing_matches
                self.illegal = illegal
                self.constraint_violations = constraint_violations
                self.badarch = badarch
                self.not_installed = not_installed
                self.installed = installed

        def __str__(self):
                res = []
                if self.unmatched_fmris:
                        s = _("""\
The following pattern(s) did not match any packages in the current catalog.
Try relaxing the pattern, refreshing and/or examining the catalogs:""")
                        res += [s]
                        res += ["\t%s" % p for p in self.unmatched_fmris]

                if self.multiple_matches:
                        s = _("'%s' matches multiple packages")
                        for p, lst in self.multiple_matches:
                                res.append(s % p)
                                for pfmri in lst:
                                        res.append("\t%s" % pfmri)

                s = _("'%s' matches no installed packages")
                res += [ s % p for p in self.missing_matches ]

                s = _("'%s' is an illegal fmri")
                res += [ s % p for p in self.illegal ]

                if self.constraint_violations:
                        s = _("The following package(s) violated constraints:")
                        res += [s]
                        res += ["\t%s" % p for p in self.constraint_violations]

                if self.badarch:
                        s = _("'%s' supports the following architectures: %s")
                        a = _("Image architecture is defined as: %s")
                        res += [ s % (self.badarch[0],
                            ", ".join(self.badarch[1]))]
                        res += [ a % (self.badarch[2])]

                if self.not_installed:
                        s = _("The proposed operation can not be performed for "
                            "the following package(s) as they are not "
                            "installed: ")
                        res += [s]
                        res += ["\t%s" % p for p in self.not_installed]

                if self.installed:
                        s = _("The proposed operation can not be performed for "
                            "the following package(s) as they are already "
                            "installed: ")
                        res += [s]
                        res += ["\t%s" % p for p in self.installed]

                return "\n".join(res)


class ActionExecutionError(ApiException):
        """An error was encountered executing an action.

        In particular, this exception indicates that something went wrong in the
        application (or unapplication) of the action to the system, not an error
        in the pkg(5) code.

        The 'msg' argument can provide a more specific message than what would
        be returned from, and 'ignoreerrno' can be set to True to indicate that
        the sterror() text is misleading, and shouldn't be displayed.
        """

        def __init__(self, action, exception, msg=None, ignoreerrno=False):
                self.action = action
                self.exception = exception
                self.msg = msg
                self.ignoreerrno = ignoreerrno

        def __str__(self):
                errno = ""
                if not self.ignoreerrno and hasattr(self.exception, "errno"):
                        errno = "[errno %d: %s]" % (self.exception.errno,
                            os.strerror(self.exception.errno))

                msg = self.msg or ""

                # Fall back on the wrapped exception if we don't have anything
                # useful.
                if not errno and not msg:
                        return str(self.exception)

                if errno and msg:
                        return "%s: %s" % (errno, msg)

                # If we only have one of the two, no need for the colon.
                return "%s%s" % (errno, msg)


class CatalogRefreshException(ApiException):
        def __init__(self, failed, total, succeeded, message=None):
                ApiException.__init__(self)
                self.failed = failed
                self.total = total
                self.succeeded = succeeded
                self.message = message


class CatalogError(ApiException):
        """Base exception class for all catalog exceptions."""

        def __init__(self, *args, **kwargs):
                ApiException.__init__(self)
                if args:
                        self.data = args[0]
                else:
                        self.data = None
                self.args = kwargs

        def __str__(self):
                return str(self.data)


class AnarchicalCatalogFMRI(CatalogError):
        """Used to indicate that the specified FMRI is not valid for catalog
        operations because it is missing publisher information."""

        def __str__(self):
                return _("The FMRI '%s' does not contain publisher information "
                    "and cannot be used for catalog operations.") % self.data


class BadCatalogMetaRoot(CatalogError):
        """Used to indicate an operation on the catalog's meta_root failed
        because the meta_root is invalid."""

        def __str__(self):
                return _("Catalog meta_root '%(root)s' is invalid; unable "
                    "to complete operation: '%(op)s'.") % { "root": self.data,
                    "op": self.args.get("operation", None) }


class BadCatalogPermissions(CatalogError):
        """Used to indicate the server catalog files do not have the expected
        permissions."""

        def __init__(self, files):
                """files should contain a list object with each entry consisting
                of a tuple of filename, expected_mode, received_mode."""
                if not files:
                        files = []
                CatalogError.__init__(self, files)

        def __str__(self):
                msg = _("The following catalog files have incorrect "
                    "permissions:\n")
                for f in self.args:
                        fname, emode, fmode = f
                        msg += _("\t%(fname)s: expected mode: %(emode)s, found "
                            "mode: %(fmode)s\n") % { "fname": fname,
                            "emode": emode, "fmode": fmode }
                return msg


class BadCatalogSignatures(CatalogError):
        """Used to indicate that the Catalog signatures are not valid."""

        def __str__(self):
                return _("The signature data for the '%s' catalog file is not "
                    "valid.") % self.data


class BadCatalogUpdateIdentity(CatalogError):
        """Used to indicate that the requested catalog updates could not be
        applied as the new catalog data is significantly different such that
        the old catalog cannot be updated to match it."""

        def __str__(self):
                return _("Unable to determine the updates needed for  "
                    "the current catalog using the provided catalog "
                    "update data in '%s'.") % self.data


class DuplicateCatalogEntry(CatalogError):
        """Used to indicate that the specified catalog operation could not be
        performed since it would result in a duplicate catalog entry."""

        def __str__(self):
                return _("Unable to perform '%(op)s' operation for catalog "
                    "%(name)s; completion would result in a duplicate entry "
                    "for package '%(fmri)s'.") % { "op": self.args.get(
                    "operation", None), "name": self.args.get("catalog_name",
                    None), "fmri": self.data }


class CatalogUpdateRequirements(CatalogError):
        """Used to indicate that an update request for the catalog could not
        be performed because update requirements were not satisfied."""

        def __str__(self):
                return _("Catalog updates can only be applied to an on-disk "
                    "catalog.")


class InvalidCatalogFile(CatalogError):
        """Used to indicate a Catalog file could not be loaded."""

        def __str__(self):
                return _("Catalog file '%s' is invalid.") % self.data


class ObsoleteCatalogUpdate(CatalogError):
        """Used to indicate that the specified catalog updates are for an older
        version of the catalog and cannot be applied."""

        def __str__(self):
                return _("Unable to determine the updates needed for the "
                    "catalog using the provided catalog update data in '%s'. "
                    "The specified catalog updates are for an older version "
                    "of the catalog and cannot be used.") % self.data


class UnknownCatalogEntry(CatalogError):
        """Used to indicate that an entry for the specified package FMRI or
        pattern could not be found in the catalog."""

        def __str__(self):
                return _("'%s' could not be found in the catalog.") % self.data


class UnknownUpdateType(CatalogError):
        """Used to indicate that the specified CatalogUpdate operation is
        unknown."""

        def __str__(self):
                return _("Unknown catalog update type '%s'") % self.data


class UnrecognizedCatalogPart(CatalogError):
        """Raised when the catalog finds a CatalogPart that is unrecognized
        or invalid."""

        def __str__(self):
                return _("Unrecognized, unknown, or invalid CatalogPart '%s'") \
                    % self.data


class InventoryException(ApiException):
        """Used to indicate that some of the specified patterns to a catalog
        matching function did not match any catalog entries."""

        def __init__(self, illegal=EmptyI, matcher=EmptyI, notfound=EmptyI,
            publisher=EmptyI, version=EmptyI):
                ApiException.__init__(self)
                self.illegal = illegal
                self.matcher = matcher
                self.notfound = set(notfound)
                self.publisher = publisher
                self.version = version

                self.notfound.update(matcher)
                self.notfound.update(publisher)
                self.notfound.update(version)
                self.notfound = list(self.notfound)

                assert self.illegal or self.notfound 

        def __str__(self):
                outstr = ""
                for x in self.illegal:
                        # Illegal FMRIs have their own __str__ method
                        outstr += "%s\n" % x

                if self.matcher or self.publisher or self.version:
                        outstr += _("No matching package could be found for "
                            "the following FMRIs in any of the catalogs for "
                            "the current publishers:\n")

                        for x in self.matcher:
                                outstr += _("%s (pattern did not match)\n") % x
                        for x in self.publisher:
                                outstr += _("%s (publisher did not "
                                    "match)\n") % x
                        for x in self.version:
                                outstr += _("%s (version did not match)\n") % x
                return outstr


# SearchExceptions

class SearchException(ApiException):
        """Based class used for all search-related api exceptions."""
        pass


class MainDictParsingException(SearchException):
        """This is used when the main dictionary could not parse a line."""
        def __init__(self, e):
                SearchException.__init__(self)
                self.e = e

        def __str__(self):
                return str(self.e)


class MalformedSearchRequest(SearchException):
        """Raised when the server cannot understand the format of the
        search request."""

        def __init__(self, url):
                SearchException.__init__(self)
                self.url = url

        def __str__(self):
                return str(self.url)


class NegativeSearchResult(SearchException):
        """Returned when the search cannot find any matches."""

        def __init__(self, url):
                SearchException.__init__(self)
                self.url = url

        def __str__(self):
                return _("The search at url %s returned no results.") % self.url


class ProblematicSearchServers(SearchException):
        """This class wraps exceptions which could appear while trying to
        do a search request."""

        def __init__(self, failed=EmptyI, invalid=EmptyI, unsupported=EmptyI):
                SearchException.__init__(self)
                self.failed_servers = failed
                self.invalid_servers  = invalid
                self.unsupported_servers = unsupported

        def __str__(self):
                s = _("Some servers failed to respond appropriately:\n")
                for pub, err in self.failed_servers:
                        s += _("%(o)s:\n%(msg)s\n") % \
                            { "o": pub, "msg": err}
                for pub in self.invalid_servers:
                        s += _("%s did not return a valid response.\n" \
                            % pub)
                if len(self.unsupported_servers) > 0:
                        s += _("Some servers don't support requested search"
                            " operation:\n")
                for pub, err in self.unsupported_servers:
                        s += _("%(o)s:\n%(msg)s\n") % \
                            { "o": pub, "msg": err}

                return s


class SlowSearchUsed(SearchException):
        """This exception is thrown when a local search is performed without
        an index.  It's raised after all results have been yielded."""

        def __str__(self):
                return _("Search performance is degraded.\n"
                    "Run 'pkg rebuild-index' to improve search speed.")


class UnsupportedSearchError(SearchException):
        """Returned when a search protocol is not supported by the
        remote server."""

        def __init__(self, url=None, proto=None):
                SearchException.__init__(self)
                self.url = url
                self.proto = proto

        def __str__(self):
                s = _("Search server does not support the requested protocol:")
                if self.url:
                        s += "\nServer URL: %s" % self.url
                if self.proto:
                        s += "\nRequested operation: %s" % self.proto
                return s

        def __cmp__(self, other):
                if not isinstance(other, UnsupportedSearchError):
                        return -1        
                r = cmp(self.url, other.url)
                if r != 0:
                        return r
                return cmp(self.proto, other.proto)


# IndexingExceptions.

class IndexingException(SearchException):
        """ The base class for all exceptions that can occur while indexing. """

        def __init__(self, private_exception):
                SearchException.__init__(self)
                self.cause = private_exception.cause


class CorruptedIndexException(IndexingException):
        """This is used when the index is not in a correct state."""
        pass


class InconsistentIndexException(IndexingException):
        """This is used when the existing index is found to have inconsistent
        versions."""
        def __init__(self, e):
                IndexingException.__init__(self, e)
                self.exception = e

        def __str__(self):
                return str(self.exception)


class ProblematicPermissionsIndexException(IndexingException):
        """ This is used when the indexer is unable to create, move, or remove
        files or directories it should be able to. """
        def __str__(self):
                return "Could not remove or create " \
                    "%s because of incorrect " \
                    "permissions. Please correct this issue then " \
                    "rebuild the index." % self.cause

class WrapIndexingException(ApiException):
        """This exception is used to wrap an indexing exception during install,
        uninstall, or image-update so that a more appropriate error message
        can be displayed to the user."""

        def __init__(self, e, tb, stack):
                ApiException.__init__(self)
                self.wrapped = e
                self.tb = tb
                self.stack = stack

        def __str__(self):
                tmp = self.tb.split("\n")
                res = tmp[:1] + [s.rstrip("\n") for s in self.stack] + tmp[1:]
                return "\n".join(res)


class WrapSuccessfulIndexingException(WrapIndexingException):
        """This exception is used to wrap an indexing exception during install,
        uninstall, or image-update which was recovered from by performing a
        full reindex."""
        pass


# Query Parsing Exceptions
class BooleanQueryException(ApiException):
        """This exception is used when the children of a boolean operation
        have different return types.  The command 'pkg search foo AND <bar>'
        is the simplest example of this."""

        def __init__(self, e):
                ApiException.__init__(self)
                self.e = e

        def __str__(self):
                return str(self.e)


class ParseError(ApiException):
        def __init__(self, e):
                ApiException.__init__(self)
                self.e = e

        def __str__(self):
                return str(self.e)


class NonLeafPackageException(ApiException):
        """Removal of a package which satisfies dependencies has been attempted.

        The first argument to the constructor is the FMRI which we tried to
        remove, and is available as the "fmri" member of the exception.  The
        second argument is the list of dependent packages that prevent the
        removal of the package, and is available as the "dependents" member.
        """

        def __init__(self, *args):
                ApiException.__init__(self, *args)

                self.fmri = args[0]
                self.dependents = args[1]

class InvalidDepotResponseException(ApiException):
        """Raised when the depot doesn't have versions of operations
        that the client needs to operate successfully."""
        def __init__(self, url, data):
                ApiException.__init__(self)
                self.url = url
                self.data = data

        def __str__(self):
                s = "Unable to contact valid package server"
                if self.url:
                        s += ": %s" % self.url
                if self.data:
                        s += "\nEncountered the following error(s):\n%s" % \
                            self.data
                return s

class DataError(ApiException):
        """Base exception class used for all data related errors."""

        def __init__(self, *args, **kwargs):
                ApiException.__init__(self, *args)
                if args:
                        self.data = args[0]
                else:
                        self.data = None
                self.args = kwargs


class InvalidP5IFile(DataError):
        """Used to indicate that the specified location does not contain a
        valid p5i-formatted file."""

        def __str__(self):
                if self.data:
                        return _("The specified file is in an unrecognized "
                            "format or does not contain valid publisher "
                            "information: %s") % self.data
                return _("The specified file is in an unrecognized format or "
                    "does not contain valid publisher information.")


class UnsupportedP5IFile(DataError):
        """Used to indicate that an attempt to read an unsupported version
        of pkg(5) info file was attempted."""

        def __str__(self):
                return _("Unsupported pkg(5) publisher information data "
                    "format.")


class TransportError(ApiException):
        """Abstract exception class for all transport exceptions.
        Specific transport exceptions should be implemented in the
        transport code.  Callers wishing to catch transport exceptions
        should use this class.  Subclasses must implement all methods
        defined here that raise NotImplementedError."""

        def __str__(self):
                raise NotImplementedError


class RetrievalError(ApiException):
        """Used to indicate that a a requested resource could not be
        retrieved."""

        def __init__(self, data, location=None):
                ApiException.__init__(self)
                self.data = data
                self.location = location

        def __str__(self):
                if self.location:
                        return _("Error encountered while retrieving data from "
                            "'%s':\n%s") % (self.location, self.data)
                return _("Error encountered while retrieving data from: %s") % \
                    self.data


class InvalidResourceLocation(ApiException):
        """Used to indicate that an invalid transport location was provided."""

        def __init__(self, data):
                ApiException.__init__(self)
                self.data = data

        def __str__(self):
                return _("'%s' is not a valid location.") % self.data

class BEException(ApiException):
        def __init__(self):
                ApiException.__init__(self)

class InvalidBENameException(BEException):
        def __init__(self, be_name):
                BEException.__init__(self)
                self.be_name = be_name

        def __str__(self):
                return _("'%s' is not a valid boot environment name.") % \
                    self.be_name

class DuplicateBEName(BEException):
        """Used to indicate that there is an existing boot environment 
        with this name"""

        def __init__(self, be_name):
                BEException.__init__(self)
                self.be_name = be_name

        def __str__(self):
                return _("The boot environment '%s' already exists.") % \
                    self.be_name

class BENamingNotSupported(BEException):
        def __init__(self, be_name):
                BEException.__init__(self)
                self.be_name = be_name

        def __str__(self):
                return _("""\
Boot environment naming during package install is not supported on this
version of OpenSolaris. Please image-update without the --be-name option.""")

class UnableToCopyBE(BEException):
        def __str__(self):
                return _("Unable to clone the current boot environment.")

class UnableToRenameBE(BEException):
        def __init__(self, orig, dest):
                BEException.__init__(self)
                self.original_name = orig
                self.destination_name = dest

        def __str__(self):
                d = {
                    "orig": self.original_name,
                    "dest": self.destination_name
                }
                return _("""\
A problem occurred while attempting to rename the boot environment
currently named %(orig)s to %(dest)s.""") % d

class UnableToMountBE(BEException):
        def __init__(self, be_name, be_dir):
                BEException.__init__(self)
                self.name = be_name
                self.mountpoint = be_dir

        def __str__(self):
                return _("Unable to mount %(name)s at %(mt)s") % \
                    {"name": self.name, "mt": self.mountpoint}

class BENameGivenOnDeadBE(BEException):
        def __init__(self, be_name):
                BEException.__init__(self)
                self.name = be_name

        def __str__(self):
                return _("""\
Naming a boot environment when operating on a non-live image is
not allowed.""")


class UnrecognizedOptionsToInfo(ApiException):
        def __init__(self, opts):
                ApiException.__init__(self)
                self._opts = opts

        def __str__(self):
                s = _("Info does not recognize the following options:")
                for o in self._opts:
                        s += _(" '") + str(o) + _("'")
                return s

class IncorrectIndexFileHash(ApiException):
        """This is used when the index hash value doesn't match the hash of the
        packages installed in the image."""
        pass


class PublisherError(ApiException):
        """Base exception class for all publisher exceptions."""

        def __init__(self, *args, **kwargs):
                ApiException.__init__(self, *args)
                if args:
                        self.data = args[0]
                else:
                        self.data = None
                self.args = kwargs

        def __str__(self):
                return str(self.data)


class BadPublisherMetaRoot(PublisherError):
        """Used to indicate an operation on the publisher's meta_root failed
        because the meta_root is invalid."""

        def __str__(self):
                return _("Publisher meta_root '%(root)s' is invalid; unable "
                    "to complete operation: '%(op)s'.") % { "root": self.data,
                    "op": self.args.get("operation", None) }


class BadPublisherPrefix(PublisherError):
        """Used to indicate that a publisher name is not valid."""

        def __str__(self):
                return _("'%s' is not a valid publisher name.") % self.data


class BadRepositoryAttributeValue(PublisherError):
        """Used to indicate that the specified repository attribute value is
        invalid."""

        def __str__(self):
                return _("'%(value)s' is not a valid value for repository "
                    "attribute '%(attribute)s'.") % {
                    "value": self.args["value"], "attribute": self.data }


class BadRepositoryCollectionType(PublisherError):
        """Used to indicate that the specified repository collection type is
        invalid."""

        def __init__(self, *args, **kwargs):
                PublisherError.__init__(self, *args, **kwargs)

        def __str__(self):
                return _("'%s' is not a valid repository collection type.") % \
                    self.data


class BadRepositoryURI(PublisherError):
        """Used to indicate that a repository URI is not syntactically valid."""

        def __str__(self):
                return _("'%s' is not a valid URI.") % self.data


class BadRepositoryURIPriority(PublisherError):
        """Used to indicate that the priority specified for a repository URI is
        not valid."""

        def __str__(self):
                return _("'%s' is not a valid URI priority; integer value "
                    "expected.") % self.data


class BadRepositoryURISortPolicy(PublisherError):
        """Used to indicate that the specified repository URI sort policy is
        invalid."""

        def __init__(self, *args, **kwargs):
                PublisherError.__init__(self, *args, **kwargs)

        def __str__(self):
                return _("'%s' is not a valid repository URI sort policy.") % \
                    self.data


class DisabledPublisher(PublisherError):
        """Used to indicate that an attempt to use a disabled publisher occurred
        during an operation."""

        def __str__(self):
                return _("Publisher '%s' is disabled and cannot be used for "
                    "packaging operations.") % self.data


class DuplicatePublisher(PublisherError):
        """Used to indicate that a publisher with the same name or alias already
        exists for an image."""

        def __str__(self):
                return _("A publisher with the same name or alias as '%s' "
                    "already exists.") % self.data


class DuplicateRepository(PublisherError):
        """Used to indicate that a repository with the same origin uris
        already exists for a publisher."""

        def __str__(self):
                return _("A repository with the same name or origin URIs "
                   "already exists for publisher '%s'.") % self.data


class DuplicateRepositoryMirror(PublisherError):
        """Used to indicate that a repository URI is already in use by another
        repository mirror."""

        def __str__(self):
                return _("Mirror '%s' already exists for the specified "
                    "repository.") % self.data


class DuplicateRepositoryOrigin(PublisherError):
        """Used to indicate that a repository URI is already in use by another
        repository origin."""

        def __str__(self):
                return _("Origin '%s' already exists for the specified "
                    "repository.") % self.data


class RemovePreferredPublisher(PublisherError):
        """Used to indicate an attempt to remove the preferred publisher was
        made."""

        def __str__(self):
                return _("The preferred publisher cannot be removed.")


class SelectedRepositoryRemoval(PublisherError):
        """Used to indicate that an attempt to remove the selected repository
        for a publisher was made."""

        def __str__(self):
                return _("Cannot remove the selected repository for a "
                    "publisher.")


class SetDisabledPublisherPreferred(PublisherError):
        """Used to indicate an attempt to set a disabled publisher as the
        preferred publisher was made."""

        def __str__(self):
                return _("Publisher '%s' is disabled and cannot be set as the "
                    "preferred publisher.") % self.data


class SetPreferredPublisherDisabled(PublisherError):
        """Used to indicate that an attempt was made to set the preferred
        publisher as disabled."""

        def __str__(self):
                return _("The preferred publisher may not be disabled."
                    "  Another publisher must be set as the preferred "
                    "publisher before this publisher can be disabled.")


class UnknownLegalURI(PublisherError):
        """Used to indicate that no matching legal URI could be found using the
        provided criteria."""

        def __str__(self):
                return _("Unknown legal URI '%s'.") % self.data


class UnknownPublisher(PublisherError):
        """Used to indicate that no matching publisher could be found using the
        provided criteria."""

        def __str__(self):
                return _("Unknown publisher '%s'.") % self.data


class UnknownRelatedURI(PublisherError):
        """Used to indicate that no matching related URI could be found using
        the provided criteria."""

        def __str__(self):
                return _("Unknown related URI '%s'.") % self.data


class UnknownRepository(PublisherError):
        """Used to indicate that no matching repository could be found using the
        provided criteria."""

        def __str__(self):
                return _("Unknown repository '%s'.") % self.data


class UnknownRepositoryMirror(PublisherError):
        """Used to indicate that a repository URI could not be found in the
        list of repository mirrors."""

        def __str__(self):
                return _("Unknown repository mirror '%s'.") % self.data

class UnsupportedRepositoryOperation(PublisherError):
        """The publisher has no active repositories that support the
        requested operation."""

        def __init__(self, pub, operation):
                ApiException.__init__(self)
                self.data = None
                self.kwargs = None
                self.pub = pub
                self.op = operation

        def __str__(self):
                return _("Publisher '%s' has no repositories that support the"
                    " '%s' operation.") % (self.pub.prefix, self.op)

class UnknownRepositoryOrigin(PublisherError):
        """Used to indicate that a repository URI could not be found in the
        list of repository origins."""

        def __str__(self):
                return _("Unknown repository origin '%s'") % self.data


class UnsupportedRepositoryURI(PublisherError):
        """Used to indicate that the specified repository URI uses an
        unsupported scheme."""

        def __str__(self):
                if self.data:
                        scheme = urlparse.urlsplit(self.data,
                            allow_fragments=0)[0]
                        return _("The URI '%(uri)s' contains an unsupported "
                            "scheme '%(scheme)s'.") % { "uri": self.data,
                            "scheme": scheme }
                return _("The specified URI contains an unsupported scheme.")


class UnsupportedRepositoryURIAttribute(PublisherError):
        """Used to indicate that the specified repository URI attribute is not
        supported for the URI's scheme."""

        def __str__(self):
                return _("'%(attr)s' is not supported for '%(scheme)s'.") % {
                    "attr": self.data, "scheme": self.args["scheme"] }


class CertificateError(ApiException):
        """Base exception class for all certificate exceptions."""

        def __init__(self, *args, **kwargs):
                ApiException.__init__(self, *args)
                if args:
                        self.data = args[0]
                else:
                        self.data = None
                self.args = kwargs

        def __str__(self):
                return str(self.data)


class ExpiredCertificate(CertificateError):
        """Used to indicate that a certificate has expired."""

        def __str__(self):
                publisher = self.args.get("publisher", None)
                uri = self.args.get("uri", None)
                if publisher:
                        if uri:
                                return _("Certificate '%(cert)s' for publisher "
                                    "'%(pub)s' needed to access '%(uri)s', "
                                    "has expired.  Please install a valid "
                                    "certificate.") % { "cert": self.data,
                                    "pub": publisher, "uri": uri }
                        return _("Certificate '%(cert)s' for publisher "
                            "'%(pub)s', has expired.  Please install a valid "
                            "certificate.") % { "cert": self.data,
                            "pub": publisher }
                if uri:
                        return _("Certificate '%(cert)s', needed to access "
                            "'%(uri)s', has expired.  Please install a valid "
                            "certificate.") % { "cert": self.data, "uri": uri }
                return _("Certificate '%s' has expired.  Please install a "
                    "valid certificate.") % self.data


class ExpiringCertificate(CertificateError):
        """Used to indicate that a certificate has expired."""

        def __str__(self):
                publisher = self.args.get("publisher", None)
                uri = self.args.get("uri", None)
                days = self.args.get("days", 0)
                if publisher:
                        if uri:
                                return _("Certificate '%(cert)s' for publisher "
                                    "'%(pub)s', needed to access '%(uri)s', "
                                    "will expire in '%(days)s' days.") % {
                                    "cert": self.data, "pub": publisher,
                                    "uri": uri, "days": days }
                        return _("Certificate '%(cert)s' for publisher "
                            "'%(pub)s' will expire in '%(days)s' days.") % {
                            "cert": self.data, "pub": publisher, "days": days }
                if uri:
                        return _("Certificate '%(cert)s', needed to access "
                            "'%(uri)s', will expire in '%(days)s' days.") % {
                            "cert": self.data, "uri": uri, "days": days }
                return _("Certificate '%(cert)s' will expire in "
                    "'%(days)s' days.") % { "cert": self.data, "days": days }


class InvalidCertificate(CertificateError):
        """Used to indicate that a certificate is invalid."""

        def __str__(self):
                publisher = self.args.get("publisher", None)
                uri = self.args.get("uri", None)
                if publisher:
                        if uri:
                                return _("Certificate '%(cert)s' for publisher "
                                    "'%(pub)s', needed to access '%(uri)s', is "
                                    "invalid.") % { "cert": self.data,
                                    "pub": publisher, "uri": uri }
                        return _("Certificate '%(cert)s' for publisher "
                            "'%(pub)s' is invalid.") % { "cert": self.data,
                            "pub": publisher }
                if uri:
                        return _("Certificate '%(cert)s' needed to access "
                            "'%(uri)s' is invalid.") % { "cert": self.data,
                            "uri": uri }
                return _("Invalid certificate '%s'.") % self.data


class NoSuchKey(CertificateError):
        """Used to indicate that a key could not be found."""

        def __str__(self):
                publisher = self.args.get("publisher", None)
                uri = self.args.get("uri", None)
                if publisher:
                        if uri:
                                return _("Unable to locate key '%(key)s' for "
                                    "publisher '%(pub)s' needed to access "
                                    "'%(uri)s'.") % { "key": self.data,
                                    "pub": publisher, "uri": uri }
                        return _("Unable to locate key '%(key)s' for publisher "
                            "'%(pub)s'.") % { "key": self.data, "pub": publisher
                            }
                if uri:
                        return _("Unable to locate key '%(key)s' needed to "
                            "access '%(uri)s'.") % { "key": self.data,
                            "uri": uri }
                return _("Unable to locate key '%s'.") % self.data


class NoSuchCertificate(CertificateError):
        """Used to indicate that a certificate could not be found."""

        def __str__(self):
                publisher = self.args.get("publisher", None)
                uri = self.args.get("uri", None)
                if publisher:
                        if uri:
                                return _("Unable to locate certificate "
                                    "'%(cert)s' for publisher '%(pub)s' needed "
                                    "to access '%(uri)s'.") % {
                                    "cert": self.data, "pub": publisher,
                                    "uri": uri }
                        return _("Unable to locate certificate '%(cert)s' for "
                            "publisher '%(pub)s'.") % { "cert": self.data,
                            "pub": publisher }
                if uri:
                        return _("Unable to locate certificate '%(cert)s' "
                            "needed to access '%(uri)s'.") % {
                            "cert": self.data, "uri": uri }
                return _("Unable to locate certificate '%s'.") % self.data


class NotYetValidCertificate(CertificateError):
        """Used to indicate that a certificate is not yet valid (future
        effective date)."""

        def __str__(self):
                publisher = self.args.get("publisher", None)
                uri = self.args.get("uri", None)
                if publisher:
                        if uri:
                                return _("Certificate '%(cert)s' for publisher "
                                    "'%(pub)s', needed to access '%(uri)s', "
                                    "has a future effective date.") % {
                                    "cert": self.data, "pub": publisher,
                                    "uri": uri }
                        return _("Certificate '%(cert)s' for publisher "
                            "'%(pub)s' has a future effective date.") % {
                            "cert": self.data, "pub": publisher }
                if uri:
                        return _("Certificate '%(cert)s' needed to access "
                            "'%(uri)s' has a future effective date.") % {
                            "cert": self.data, "uri": uri }
                return _("Certificate '%s' has a future effective date.") % \
                    self.data


class ServerReturnError(ApiException):
        """This exception is used when the server reutrns a line which the
        client cannot parse correctly."""

        def __init__(self, line):
                ApiException.__init__(self)
                self.line = line

        def __str__(self):
                return _("Gave a bad response:%s") % self.line


class MissingFileArgumentException(ApiException):
        """This exception is used when a file was given as an argument but
        no such file could be found."""
        def __init__(self, path):
                ApiException.__init__(self)
                self.path = path

        def __str__(self):
                return _("Could not find %s") % self.path


class ManifestError(ApiException):
        """Base exception class for all manifest exceptions."""

        def __init__(self, *args, **kwargs):
                ApiException.__init__(self, *args, **kwargs)
                if args:
                        self.data = args[0]
                else:
                        self.data = None
                self.args = kwargs

        def __str__(self):
                return str(self.data)


class BadManifestSignatures(ManifestError):
        """Used to indicate that the Manifest signatures are not valid."""

        def __str__(self):
                if self.data:
                        return _("The signature data for the manifest of the "
                            "'%s' package is not valid.") % self.data
                return _("The signature data for the manifest is not valid.")

# Image creation exceptions
class ImageCreationException(ApiException):
        def __init__(self, path):
                self.path = path

        def __str__(self):
                raise NotImplementedError()


class ImageAlreadyExists(ImageCreationException):
        def __str__(self):
                return _("there is already an image at: %s.\nTo override, use "
                    "the -f (force) option.") % self.path


class CreatingImageInNonEmptyDir(ImageCreationException):
        def __str__(self):
                return _("the specified image path is not empty: %s.\nTo "
                    "override, use the -f (force) option.") % self.path
