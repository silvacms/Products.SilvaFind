import os
import unittest
from Products.Five.testbrowser import Browser
from Products.Silva.converters import PDF_TO_TEXT_AVAILABLE
from Products.Silva.tests.SilvaBrowser import SilvaBrowser
from Products.Silva.tests.SilvaTestCase import SilvaFunctionalTestCase

content = {
    'the_great_figure': {
        'id': 'the_great_figure',
        'title': 'The Great Figure',
        'file': 'the_great_figure.pdf',
        'full_text': 'gold',
        'short_title': '',
        'keywords': 'williams',
    },
    'the_raven': {
        'id': 'the_raven',
        'title': 'The Raven',
        'file': 'raven.txt',
        'full_text': 'bleak',
        'short_title': '',
        'keywords': 'poe',
    },
    'the_second_coming': {
        'id': 'the_second_coming',
        'title': 'The Second Coming',
        'file': 'the_second_coming.txt',
        'full_text': 'Spiritus Mundi',
        'short_title': '',
        'keywords': 'yeats',
    },
}



class SilvaFindTestCase(SilvaFunctionalTestCase):
    """
        check if machine has pdftotext
        if pdftotext is present run all tests, if not leave out pdftotext tests.
        test search results of SilvaFind
    """

    def content(self, sb, pdf=True):
        directory = os.path.dirname(__file__)
        for text_name, text_attribute in content.iteritems():
            file_handle = open(os.path.join(directory,
                                            text_attribute['file']))
            file_data = file_handle.read()
            file_handle.seek(0)
            self.root.manage_addProduct['Silva'].manage_addFile(
                text_attribute['id'], text_attribute['title'], file_handle)
            file_handle.close()

        sb.make_content('Silva Find', id='search_test',
                                      title='Search test')
        
        ids = sb.get_content_ids()
        self.failUnless('search_test' in ids)

        if pdf:
            ids = sb.get_content_ids()
            self.failUnless('the_raven' in ids)
            self.failUnless('the_second_coming' in ids)
            self.failUnless('the_great_figure' in ids)
        else:
            for text_name, text_attribute in content.iteritems():
                if text_attribute['id'] != 'the_great_figure':
                    sb.make_content('Silva File', id=text_attribute['id'],
                                                  title=text_attribute['title'],
                                                  file=text_attribute['file'])
            
                    ids = sb.get_content_ids()
                    self.failUnless('the_raven' in ids)
                    self.failUnless('second_coming' in ids)
                else:
                    continue

    def modify_text_metadata(self, sb):
        for text_name, text_attribute in content.iteritems():
            sb.click_href_labeled(text_name)
            sb.click_tab_named('properties')
            sb.browser.getControl(name='silva-extra.keywords:record').value = text_attribute['keywords']
            sb.browser.getControl(name='save_metadata:method', index=0).click()
            self.failUnless(text_attribute['keywords'] in sb.browser.contents)
            sb.click_href_labeled('edit')
            sb.click_href_labeled('root')

    def modify_interface(self, sb, keyword):
        sb.click_href_labeled('search_test')
        checkbox = sb.browser.getControl(name='meta_type:list')
        form = sb.browser.getForm(index=0)
        form.getControl(name='show_meta_type:bool').value = ['checked']
        form.getControl(name='show_silva-content-maintitle:bool').value = ['checked']
        form.getControl(name='show_silva-extra-keywords:bool').value = ['checked']
        form.getControl(name='silva-extra.keywords:record').value = keyword
        form.submit()
        form = sb.browser.getForm(index=0)
        self.assertEquals(form.getControl(name='show_meta_type:bool').value, True)
        self.assertEquals(form.getControl(name='show_silva-content-maintitle:bool').value, True)
        self.assertEquals(form.getControl(name='show_silva-extra-keywords:bool').value, True)
        self.assertEquals(form.getControl(name='silva-extra.keywords:record').value, keyword)
        sb.click_href_labeled('root')
    
    def search(self, sb, text_id, title, full_text, pdf=True):
        """ search terms
            the_great_figure: gold
            the_second_coming: falcon
            the_raven: raven
        """
        sb.click_href_labeled('search_test')
        sb.click_href_labeled('view public version')
        if pdf:
            link = sb.browser.getLink(title)
            self.failUnless(link.text in sb.browser.contents)
            sb.browser.getControl(name='fulltext').value = full_text
            sb.browser.getControl(name='silva-content.maintitle:record').value = title
            sb.click_button_labeled('Search')
            self.failUnless(full_text in sb.browser.contents)
        else:
            print 'else'
        sb.go('http://nohost/root/edit')

    def test_silvafind(self):
        sb = SilvaBrowser()
        status, url = sb.login('manager', 'secret', sb.smi_url())
        self.assertEquals(status, 200)
        if PDF_TO_TEXT_AVAILABLE:
            # run SilvaFind with pdf tests
            self.content(sb)
        else:
            # run SilvaFind with no pdf tests
            print """
                  pdftotext is not installed.
                  SilvaFind test will continue without testing pdf find functionality!
                  Please install pdftotext and restart the test to fully test SilvaFind
                  """
            self.content(sb, pdf=None)
        self.modify_text_metadata(sb)
        for text_name, text_attribute in content.iteritems():
            self.modify_interface(sb, text_attribute['keywords'])
            self.search(sb, text_attribute['id'],
                            text_attribute['title'],
                            text_attribute['full_text'])
        h2 = sb.get_listing_h2()
        self.failUnless('Silva Root' in h2)
        status, url = sb.click_href_labeled('logout')
        self.assertEquals(status, 401)

def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(SilvaFindTestCase))
    return suite