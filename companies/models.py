from django.db import models
from django.conf import settings
import os


def company_document_upload_path(instance, filename):
    """Generate upload path for company documents"""
    return f'companies/{instance.company.slug}/{instance.content_type.lower()}/{filename}'


class Company(models.Model):
    """Company model for storing company information"""
    slug = models.SlugField(max_length=50, unique=True, help_text='Company identifier (e.g., amazon, google)')
    name = models.CharField(max_length=100, help_text='Display name')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Companies'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class CompanyDocument(models.Model):
    """Stores company-specific content PDFs with extracted text"""
    CONTENT_TYPE_CHOICES = (
        ('CODING', 'Coding Questions'),
        ('BEHAVIORAL', 'Behavioral Questions'),
        ('SYSTEM_DESIGN', 'System Design Questions'),
        ('PRODUCT_SENSE', 'Product Sense Cases'),
        ('ANALYTICAL', 'Analytical & Strategy Questions'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES)
    file = models.FileField(upload_to=company_document_upload_path)
    extracted_text = models.TextField(blank=True, help_text='Extracted text from PDF')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, help_text='Error details if failed')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'content_type']),
        ]
    
    def __str__(self):
        return f"{self.company.name} - {self.content_type} - {self.get_status_display()}"
