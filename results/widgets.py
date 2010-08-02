# -*- coding: utf-8 -*-
# Copyright (c) 2010 Infrae. All rights reserved.
# See also LICENSE.txt
# $Id$

import re

from Products.Silva.icon import get_icon_url
from Products.SilvaFind import schema
from Products.SilvaFind.interfaces import IResultField, IResultView
from Products.SilvaMetadata.interfaces import IMetadataService
from Products.ZCTextIndex.ParseTree import ParseError
from five import grok
from silva.core.interfaces import ISilvaObject, IVersion, IPublishable, IImage
from silva.core.views.interfaces import IVirtualSite
from zope.component import getMultiAdapter, getUtility
from zope.interface import Interface
from zope.traversing.browser import absoluteURL
from zope.traversing.browser.interfaces import IAbsoluteURL


class ResultView(grok.MultiAdapter):
    grok.implements(IResultView)
    grok.adapts(ISilvaObject, IResultField, Interface)
    grok.provides(IResultView)

    def __init__(self, context, result, request):
        self.context = context
        self.result = result
        self.request = request

    def update(self, results):
        pass

    def render(self, item):
        value = getattr(item.getObject(), self.id)()
        if not value:
            return

        if hasattr(value, 'strftime'):
            # what the hell are these things?,
            # they don't have a decent type
            value = value.strftime('%d %b %Y %H:%M')

        value = '<span class="searchresult-field-value">%s</span>' % value
        title = '<span class="searchresult-field-title">%s</span>' % (
            self.title)
        return '<span class="searchresult-field">%s%s</span>' % (title, value)


class MetatypeResultView(ResultView):
    grok.adapts(ISilvaObject, schema.MetatypeResultField, Interface)

    def render(self, item):
        content = item.getObject()
        if IVersion.providedBy(content):
            content = content.get_content()
        return '<img class="searchresult-icon" src="%s" alt="%s" />' % (
            get_icon_url(content, self.request),
            getattr(content, 'meta_type', ''))


class RankingResultView(ResultView):
    grok.adapts(ISilvaObject, schema.RankingResultField, Interface)

    def __init__(self, *args):
        super(RankingResultView, self).__init__(*args)
        self.rankings = {}
        self.highest = 1.0

    def update(self, results):
        query = self.request.form.get('fulltext')
        self.highest = 1.0
        self.rankings = {}
        if query:
            query = unicode(query, 'utf8')
            # XXX should use getUtility
            catalog = self.context.service_catalog
            index = catalog.Indexes['fulltext']
            try:
                max_index = results.start + len(results) + 1
                rankings = index.query(query, max_index)[0]
                if rankings:
                    self.highest = rankings[0][1]/100.0
                    self.rankings = dict(rankings)
            except ParseError:
                pass

        self.img = '<img alt="Rank" src="%s/++resource++Products.SilvaFind/ranking.gif"/>' % (
            IVirtualSite(self.request).get_root_url())

    def render(self, item):
        rid = item.getRID()
        if rid in self.rankings:
            return '<span class="searchresult-ranking">%s %.1f%%</span>' % (
                self.img, (self.rankings[rid] / self.highest))
        return None


class TotalResultCountView(ResultView):
    grok.adapts(ISilvaObject, schema.TotalResultCountField, Interface)

    def render(self, item):
        # the actual count is calculated in the pagetemplate
        # this is only here, so it can be enabled / disabled
        # in the smi.

        # Please note that enabling that showing the total
        # number of search results might be a security risk
        # since it can be figured out that certain objects
        # were ommitted from the search
        return None


class ResultCountView(ResultView):
    grok.adapts(ISilvaObject, schema.ResultCountField, Interface)

    def render(self, item):
        # the actual count is calculated in the pagetemplate
        # this is only here, so it can be enabled / disabled
        # in the smi.
        return


class LinkResultView(ResultView):
    grok.adapts(ISilvaObject, schema.LinkResultField, Interface)

    def render(self, item):
        content = item.getObject()
        title = content.get_title_or_id()
        if IVersion.providedBy(content):
            url = absoluteURL(content.get_content(), self.request)
        else:
            url = absoluteURL(content, self.request)
        ellipsis = '&#8230;'
        if len(title) > 50:
            title = title[:50] + ellipsis
        return '<a href="%s" class="searchresult-link">%s</a>' % (url, title)


class DateResultView(ResultView):
    grok.adapts(ISilvaObject, schema.DateResultField, Interface)

    def render(self, item):
        content = item.getObject()
        date = None
        datestr = ''
        if IPublishable.providedBy(content):
            date = content.publication_datetime()
        if date == None:
            date = content.get_modification_datetime()
        if date and hasattr(date, 'strftime'):
            datestr = date.strftime('%d %b %Y %H:%M').lower()

        return '<span class="searchresult-date">%s</span>' % datestr


class ThumbnailResultView(ResultView):
    grok.adapts(ISilvaObject, schema.ThumbnailResultField, Interface)

    def render(self, item):
        content = item.getObject()

        if not IImage.providedBy(content):
            return

        if content.thumbnail_image is None:
            return

        url = item.getURL()
        img = content.thumbnail_image.tag()
        anchor = '<a href="%s">%s</a>' % (url, img)
        return '<div class="searchresult-thumbnail">%s</div>' % anchor


class FullTextResultView(ResultView):
    grok.adapts(ISilvaObject, schema.FullTextResultField, Interface)

    def render(self, item):
        content = item.getObject()
        ellipsis = '&#8230;'
        maxwords = 40
        searchterm = unicode(self.request.form.get('fulltext', ''), 'utf8')
        catalog = self.context.service_catalog
        fulltext = catalog.getIndexDataForRID(item.getRID()).get('fulltext', [])

        if not fulltext:
            # no fulltext available, probably an image
            return ''

        # since fulltext always starts with id and title, lets remove that
        idstring = content.id
        if IVersion.providedBy(content):
            idstring = content.get_content().id
        skipwords = len(('%s %s' % (idstring, content.get_title())).split(' '))
        fulltext = fulltext[skipwords:]
        fulltextstr = ' '.join(fulltext)

        searchterms = searchterm.split()

        if not searchterms:
            # searchterm is not specified,
            # return the first 20 words
            text = ' '.join(fulltext[:maxwords])
            if IVersion.providedBy(content) and hasattr(content, 'fulltext'):
                realtext = ' '.join(content.fulltext()[2:])
                # replace multiple whitespace characters with one space
                realtext = re.compile('[\ \n\t\xa0]+').sub(' ', realtext)
                text = ' '.join(realtext.split()[:maxwords])
            if len(fulltext) > maxwords:
                text += ' ' + ellipsis
        else:
            words = maxwords / len(searchterms)
            text = []
            lowestpos = len(fulltext)
            highestpos = 0

            hilite_terms = []
            for searchterm in searchterms:
                term = re.escape(searchterm)

                if '?' in term or '*' in term:
                    termq = term.replace('\\?', '.')
                    termq = termq.replace('\\*', '.[^\ ]*')
                    term_found = re.compile(termq).findall(fulltextstr)
                    if term_found:
                        hilite_terms += term_found
                        searchterms.remove(searchterm)
                        term = term_found[0]
                        searchterms.append(term.strip())
                    else:
                        hilite_terms.append(term)
                else:
                    hilite_terms.append(term)

                if not term in fulltext:
                    # term matched probably something in the title
                    # return the first n words:
                    line = ' '.join(fulltext[:words])
                    text.append(line)
                    lowestpos = 0
                    highestpos = words
                    continue

                pos = fulltext.index(term)
                if pos < lowestpos:
                    lowestpos = pos
                if pos > highestpos:
                    highestpos = pos
                start = pos -(words/2)
                end = pos + (words/2) + 1
                if start < 0 :
                    end += -start
                    start = 0

                pre = ' '.join(fulltext[start:pos])
                post = ' '.join(fulltext[pos+1:end])

                if not text and start != 0:
                    # we're adding the first (splitted) result
                    # and it's not at the beginning of the fulltext
                    # lets add an ellipsis
                    pre = ellipsis + pre


                text.append('%s %s %s %s' % (
                                pre,
                                fulltext[pos],
                                post,
                                ellipsis)
                            )
            # if all the terms that are found are close together,
            # then use this, otherwise, we would end
            # up with the same sentence for each searchterm
            # this code will create a new text result list, which
            # does not have 'split' results.
            if lowestpos < highestpos:
                if highestpos - lowestpos < maxwords:
                    padding = (maxwords-(highestpos - lowestpos ))/2
                    lowestpos -= padding
                    highestpos += padding
                    if lowestpos < 0:
                        highestpos += -lowestpos
                        lowestpos = 0

                    text = fulltext[lowestpos:highestpos]
                    if not lowestpos == 0:
                        text[0] = '%s %s' % (ellipsis, text[0])
                    if highestpos < len(fulltext)-1:
                        text[-1] += ' %s' % ellipsis

            # do some hiliting, use original text
            # (with punctuation) if this is a silva document
            text = ' '.join(text)
            if IVersion.providedBy(content) and hasattr(content, 'fulltext'):
                realtext = ' '.join(content.fulltext()[2:])
                # replace multiple whitespace characters with one space
                realtext = re.compile('[\ \n\t\xa0]+').sub(' ', realtext)
                textparts = text.split(ellipsis)
                new = []
                for textpart in textparts:
                    if textpart == '':
                        new.append('')
                        continue
                    textpart = textpart.strip()
                    find = textpart.replace(' ', '[^a-zA-Z0-9]+')
                    textexpr = re.compile(find, re.IGNORECASE)
                    text = textexpr.findall(realtext)
                    if text:
                        text = text[0]
                    else:
                        # somehow we can't find a match in original text
                        # use the one from the catalog
                        text = textpart
                    new.append(text)
                text = ellipsis.join(new)

            for term in hilite_terms:
                if term.startswith('"'):
                    term = term[1:]
                if term.endswith('"'):
                    term = term[:-1]
                term = re.escape(term)
                text = ' ' + text
                regexp = re.compile(
                    '([^a-zA-Z0-9]+)(%s)([^a-zA-Z0-9]+)' % term.lower(),
                    re.IGNORECASE)
                sub = ('\g<1><strong class="search-result-snippet-hilite">'
                       '\g<2></strong>\g<3>')
                text = regexp.sub(sub, text)
        return '<div class="searchresult-snippet">%s</div>' % text.strip()


class BreadcrumbsResultView(ResultView):
    grok.adapts(ISilvaObject, schema.BreadcrumbsResultField, Interface)

    def render(self, item):
        content = item.getObject()
        part = []
        breadcrumb = getMultiAdapter((content, self.request), IAbsoluteURL)
        for crumb in breadcrumb.breadcrumbs()[:-1]:
            part.append('<a href="%s">%s</a>' % (crumb['url'], crumb['name']))
        part = '<span> &#183; </span>'.join(part)
        return '<span class="searchresult-breadcrumb">%s</span>' % part


class MetadataResultView(ResultView):
    grok.adapts(ISilvaObject, schema.MetadataResultField, Interface)

    def __init__(self, *args):
        super(MetadataResultView, self).__init__(*args)
        self.service = getUtility(IMetadataService)

    def render(self, item):
        set, element = self.id.split(':')

        value = self.service.getMetadataValue(
                item.getObject(), set, element)

        value = self.getMetadataElement().renderView(value)

        if not value:
            return

        #if hasattr(value, 'strftime'):
            # what the hell are these things?,
            # they don't have a decent type
            #value = value.strftime('%d %b %Y %H:%M')
        cssid = "metadata-%s-%s" % (set, element)
        result = [  '<span class="searchresult-field %s">' % cssid,

                    '<span class="searchresult-field-title">',
                    self.result.title,
                    '</span>',
                    '<span class="searchresult-field-value">',
                    value,
                    '</span>',
                    '</span>']
        # we return a list here, so the pt. can iterate it, and self.title will
        # be translated.
        return result

